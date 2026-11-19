// Stream one finalized journal. Temporary integer buffers are converted to Parquet by l01_snapshots.py.
#include <simdjson.h>
#include <zlib.h>
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>

using Json = simdjson::dom::element;
using Int = int64_t;
using namespace std::literals;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

Int scaled(std::string_view value, int decimals) {
    bool negative = !value.empty() && value.front() == '-';
    if (negative) value.remove_prefix(1);
    Int n = 0;
    int places = -1;
    require(!value.empty(), "empty decimal");
    for (char c : value) {
        if (c == '.' && places < 0) { places = 0; continue; }
        require(c >= '0' && c <= '9', "bad decimal digit");
        if (places == decimals) { require(c == '0', "off-grid decimal"); continue; }
        n = n * 10 + (c - '0');
        if (places >= 0) ++places;
    }
    for (int i = std::max(0, places); i < decimals; ++i) n *= 10;
    return negative ? -n : n;
}

std::string_view str(Json value) { return value.get_string().value(); }
Int number(Json value) { return value.get_int64().value(); }

int side_sign(std::string_view side) {
    if (side == "bid") return -1;
    require(side == "ask", "unknown side");
    return 1;
}

// Negative ticks are bid levels and positive ticks are ask levels.
using Book = std::map<Int, Int>;
Book read_book(Json value) {
    Book result;
    for (auto side : {"bid"sv, "ask"sv}) {
        for (Json pair : value[side].get_array().value()) {
            auto levels = pair.get_array().value();
            require(levels.size() == 2, "invalid price/size pair");
            auto iter = levels.begin();
            Int price = scaled(str(*iter), 4);
            ++iter;
            Int size = scaled(str(*iter), 2);
            require(price > 0 && size >= 0, "invalid snapshot");
            if (size) require(result.emplace(side_sign(side)*price, size).second, "duplicate level");
        }
    }
    return result;
}

template<size_t N> void write_row(std::ofstream &out, const std::array<Int, N> &row) {
    out.write(reinterpret_cast<const char*>(row.data()), sizeof(row));
}

struct Replay {
    Book book;
    // Quantities added, removed, and traded (last is indexed by the passive side).
    std::map<Int, std::array<Int, 3>> flows;
    bool ready = false, interrupted = false;
    Int epoch = 0, sid = -1, seq = -1, trades = 0, updates = 0, offset = 0;
    Int rows = 0, checkpoints = 0, deltas = 0, tape = 0;
    std::ofstream clock, levels;

    explicit Replay(const std::string& dir) : clock(dir + "/clock.bin", std::ios::binary),
                                               levels(dir + "/levels.bin", std::ios::binary) {
        clock.exceptions(std::ios::badbit | std::ios::failbit);
        levels.exceptions(std::ios::badbit | std::ios::failbit);
    }
    void emit(int second) {
        auto ask = book.lower_bound(0);
        Int best_bid = (ready && book.begin() != ask) ? -book.begin()->first : 0;
        Int best_ask = (ready && ask != book.end()) ? ask->first : 0;
        bool complete = ready && !interrupted && best_bid && best_ask;
        // Merge sorted keys to retain prices withdrawn completely during this second.
        auto q = book.begin();
        auto f = flows.begin();
        while (q != book.end() || f != flows.end()) {
            Int key = q == book.end() ? f->first : f == flows.end() ? q->first : std::min(f->first, q->first);
            Int qty = 0;
            std::array<Int, 3> flow{};
            if (q != book.end() && q->first == key) { qty = q->second; ++q; }
            if (f != flows.end() && f->first == key) { flow = f->second; ++f; }
            write_row(levels, std::array<Int, 5>{key, qty, flow[0], flow[1], flow[2]});
            ++offset;
        }
        write_row(clock, std::array<Int, 9>{second, epoch, seq, best_bid, best_ask, complete, trades, updates, offset});
        flows.clear();
        trades = 0; updates = 0;
        interrupted = !ready;
    }
    void apply(Json row, Json event) {
        auto kind = str(event["type"]);
        if (kind == "subscribed") return;
        Json msg = event["msg"];
        require(str(msg["market_ticker"]) == "KXBTCPERP", "unexpected market");
        if (kind == "ticker") return;
        if (kind == "trade") {
            Int price = scaled(str(msg["price"]), 4), qty = scaled(str(msg["count"]), 2);
            require(price > 0 && qty > 0, "invalid trade");
            flows[-side_sign(str(msg["taker_side"]))*price][2] += qty;
            ++trades; ++tape;
            return;
        }
        Int row_epoch = number(row["epoch"]), row_sid = number(event["sid"]), row_seq = number(event["seq"]);
        if (kind == "orderbook_snapshot") {
            book = read_book(msg);
            ready = true; interrupted = true;
            epoch = row_epoch; sid = row_sid; seq = row_seq;
            return;
        }
        require(kind == "orderbook_delta" && ready, "unexpected message or invalid book");
        require(row_epoch == epoch && row_sid == sid && row_seq == seq+1, "book sequence gap");
        Int key = side_sign(str(msg["side"])) * scaled(str(msg["price"]), 4);
        Int delta = scaled(str(msg["delta"]), 2);
        require(key != 0, "zero price");
        Int qty = (book[key] += delta);
        require(qty >= 0, "negative depth");
        if (qty == 0) book.erase(key);
        flows[key][delta < 0] += std::abs(delta);
        seq = row_seq;
        ++deltas; ++updates;
    }
    void control(Json row, std::string_view kind) {
        if (kind == "book_checkpoint") {
            Json saved = row["book"];
            require(ready && number(row["epoch"]) == epoch && number(saved["sid"]) == sid &&
                    number(saved["seq"]) == seq && read_book(saved) == book, "checkpoint mismatch");
            ++checkpoints;
        } else if (kind == "gap_start" || kind == "connected") {
            ready = false; interrupted = true; book.clear();
        } else {
            require(kind == "gap_end" && ready, "unexpected archive control");
        }
    }
};

int main(int argc, char** argv) {
    try {
        require(argc == 6, "usage: replay journal tempdir YYYY-MM-DDTHH first_second stop_second");
        gzFile gz = gzopen(argv[1], "rb");
        require(gz, "cannot open journal");
        gzbuffer(gz, 1 << 19);
        Replay state(argv[2]);
        simdjson::dom::parser parser;
        std::array<char, 1 << 16> buffer;
        std::string line;
        int first = std::stoi(argv[4]), stop = std::stoi(argv[5]), next = first, last = -1;
        while (gzgets(gz, buffer.data(), buffer.size())) {
            line.assign(buffer.data());
            while (line.back() != '\n') {
                require(gzgets(gz, buffer.data(), buffer.size()), "incomplete row");
                line += buffer.data();
            }
            Json row = parser.parse(line).value();
            ++state.rows;
            Json control;
            bool has_control = !row["control"].get(control);
            auto kind = has_control ? str(control) : ""sv;
            if (state.rows == 1) {
                require(kind == "segment_start", "missing segment header");
                Json anchor = row["book_anchor"];
                if (!anchor.is_null()) {
                    state.book = read_book(anchor); state.ready = true;
                    state.epoch = number(anchor["epoch"]); state.sid = number(anchor["sid"]); state.seq = number(anchor["seq"]);
                }
                continue;
            }
            auto stamp = str(row["received_at"]);
            require(stamp.substr(0, 13) == argv[3], "receipt crosses file's UTC hour");
            int second = ((stamp[14]-'0')*10 + stamp[15]-'0')*60 + (stamp[17]-'0')*10 + stamp[18]-'0';
            require(second >= last, "receipt seconds reversed");
            last = second;
            while (next < std::min(second, stop)) state.emit(next++);
            if (has_control) state.control(row, kind);
            else state.apply(row, row["message"]);
        }
        require(gzeof(gz) && gzclose(gz) == Z_OK, "gzip read failed");
        while (next < stop) state.emit(next++);
        state.clock.close(); state.levels.close();
        std::cout << state.rows << ' ' << state.checkpoints << ' ' << state.deltas << ' ' << state.tape << '\n';
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
