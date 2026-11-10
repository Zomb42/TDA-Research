# Shared by setup_crc.sh and kalshi_btc_crc.job; source from the repo root.
# Runtime activation uses an existing installation, without loading modules.
initialize_crc_conda() {
    if [[ -z "${CONDA_SH:-}" && -f jobs/crc_conda.local.sh ]]; then
        source jobs/crc_conda.local.sh
    fi
    if [[ -z "${CONDA_SH:-}" ]] && command -v conda >/dev/null 2>&1; then
        CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
    fi
    if [[ -z "${CONDA_SH:-}" ]]; then
        local installation
        for installation in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3"; do
            if [[ -f "$installation/etc/profile.d/conda.sh" ]]; then
                CONDA_SH="$installation/etc/profile.d/conda.sh"
                break
            fi
        done
    fi
    if [[ -z "${CONDA_SH:-}" || ! -r "$CONDA_SH" ]]; then
        echo 'Conda initialization script not found. Run bash jobs/setup_crc.sh on CRC, or set CONDA_SH to the actual conda.sh path.' >&2
        return 2
    fi
    source "$CONDA_SH"
    export PYTHONNOUSERSITE=1
}
