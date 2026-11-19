// Replay one hourly journal and write (1) the best quotes at the end of every 100 ms of receipt
// time and (2) every trade with the best quotes just before it: the book after every update
// stamped with an earlier exchange millisecond. (Within one millisecond the trade message can
// arrive before or after the book updates it caused.)
// Parsing and checks follow replay_book.cpp; every saved checkpoint must match.
#include <simdjson.h>
#include <zlib.h>
#include <array>
#include <cstdint>
#include <deque>
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

using Book = std::map<Int, Int>;  // negative keys are bids, positive keys are asks
Book read_book(Json value) {
    Book result;
    for (auto side : {"bid"sv, "ask"sv}) {
        for (Json pair : value[side].get_array().value()) {
            auto levels = pair.get_array().value();
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

struct State {
    Book book;
    bool ready = false, interrupted = false;
    Int epoch = 0, sid = -1, seq = -1, checkpoints = 0, deltas = 0, tape = 0;
    std::ofstream grid, trades;
    std::deque<std::pair<Int, std::array<Int, 5>>> recent;  // quotes after each exchange millisecond
    explicit State(const std::string& dir) : grid(dir + "/grid.bin", std::ios::binary),
                                              trades(dir + "/trades.bin", std::ios::binary) {}
    std::array<Int, 5> quotes() const {
        auto ask = book.lower_bound(0);
        bool has_bid = ready && book.begin() != ask, has_ask = ready && ask != book.end();
        Int bid = has_bid ? -book.begin()->first : 0, bid_size = has_bid ? book.begin()->second : 0;
        Int best = has_ask ? ask->first : 0, ask_size = has_ask ? ask->second : 0;
        return {bid, best, bid_size, ask_size, ready && !interrupted && bid && best};
    }
    void emit(Int slot) {
        auto q = quotes();
        write_row(grid, std::array<Int, 6>{slot, q[0], q[1], q[2], q[3], q[4]});
        interrupted = !ready;
    }
};

int main(int argc, char** argv) {
    try {
        require(argc == 5, "usage: replay_bbo journal outdir hour_start_unix_s slots");
        gzFile gz = gzopen(argv[1], "rb");
        require(gz, "cannot open journal");
        gzbuffer(gz, 1 << 19);
        State s(argv[2]);
        Int hour_ns = std::stoll(argv[3]) * 1000000000LL, slots = std::stoll(argv[4]), next = 0;
        simdjson::dom::parser parser;
        std::array<char, 1 << 16> buffer;
        std::string line;
        Int rows = 0;
        while (gzgets(gz, buffer.data(), buffer.size())) {
            line.assign(buffer.data());
            while (line.back() != '\n') {
                require(gzgets(gz, buffer.data(), buffer.size()), "incomplete row");
                line += buffer.data();
            }
            Json row = parser.parse(line).value();
            ++rows;
            Json control;
            bool has_control = !row["control"].get(control);
            auto kind = has_control ? str(control) : ""sv;
            if (rows == 1) {
                require(kind == "segment_start", "missing segment header");
                Json anchor = row["book_anchor"];
                if (!anchor.is_null()) {
                    s.book = read_book(anchor); s.ready = true;
                    s.epoch = number(anchor["epoch"]); s.sid = number(anchor["sid"]); s.seq = number(anchor["seq"]);
                }
                continue;
            }
            if (has_control) {
                if (kind == "book_checkpoint") {
                    Json saved = row["book"];
                    require(s.ready && number(row["epoch"]) == s.epoch && number(saved["sid"]) == s.sid &&
                            number(saved["seq"]) == s.seq && read_book(saved) == s.book, "checkpoint mismatch");
                    ++s.checkpoints;
                } else if (kind == "gap_start" || kind == "connected") {
                    s.ready = false; s.interrupted = true; s.book.clear(); s.recent.clear();
                } else {
                    require(kind == "gap_end" && s.ready, "unexpected archive control");
                }
                continue;
            }
            Int ns = number(row["received_unix_ns"]);
            Int slot = (ns - hour_ns) / 100000000LL;
            while (next < std::min(slot, slots)) s.emit(next++);
            Json event = row["message"];
            auto type = str(event["type"]);
            if (type == "subscribed" || type == "ticker") continue;
            Json msg = event["msg"];
            if (type == "trade") {
                Int ms = number(msg["ts_ms"]);
                auto q = s.quotes();
                Int found = 0;
                for (auto it = s.recent.rbegin(); it != s.recent.rend(); ++it)
                    if (it->first < ms) { q = it->second; found = 1; break; }
                q[4] = q[4] && found;
                Int taker_buy = str(msg["taker_side"]) == "bid";
                write_row(s.trades, std::array<Int, 9>{ns, ms, scaled(str(msg["price"]), 4),
                                                       scaled(str(msg["count"]), 2), taker_buy, q[0], q[1], q[4],
                                                       msg["is_block_trade"].get_bool().value()});
                ++s.tape;
                continue;
            }
            Int row_epoch = number(row["epoch"]), row_sid = number(event["sid"]), row_seq = number(event["seq"]);
            if (type == "orderbook_snapshot") {
                s.book = read_book(msg); s.ready = true; s.interrupted = true; s.recent.clear();
                s.epoch = row_epoch; s.sid = row_sid; s.seq = row_seq;
                continue;
            }
            require(type == "orderbook_delta" && s.ready, "unexpected message or invalid book");
            require(row_epoch == s.epoch && row_sid == s.sid && row_seq == s.seq + 1, "book sequence gap");
            Int key = side_sign(str(msg["side"])) * scaled(str(msg["price"]), 4);
            Int qty = (s.book[key] += scaled(str(msg["delta"]), 2));
            require(qty >= 0, "negative depth");
            if (qty == 0) s.book.erase(key);
            Int ms = number(msg["ts_ms"]);
            if (s.recent.empty() || ms > s.recent.back().first) s.recent.emplace_back(ms, s.quotes());
            else s.recent.back().second = s.quotes();
            if (s.recent.size() > 256) s.recent.pop_front();
            s.seq = row_seq;
            ++s.deltas;
        }
        require(gzeof(gz) && gzclose(gz) == Z_OK, "gzip read failed");
        while (next < slots) s.emit(next++);
        s.grid.close(); s.trades.close();
        std::cout << rows << ' ' << s.checkpoints << ' ' << s.deltas << ' ' << s.tape << '\n';
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
