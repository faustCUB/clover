#!/data/data/com.termux/files/usr/bin/bash

GREEN='\033[1;32m'
DIM='\033[2;32m'
CYAN='\033[1;36m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
RESET='\033[0m'

SPINNER_CHARS=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
SPINNER_PID=""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${TMPDIR:-$HOME/tmp}/clover_install.log"
mkdir -p "$(dirname "$LOG_FILE")"

clear

banner() {
    echo ""
    echo -e "${GREEN}   ██████╗██╗      ██████╗ ██╗   ██╗███████╗██████╗ ${RESET}"
    echo -e "${GREEN}  ██╔════╝██║     ██╔═══██╗██║   ██║██╔════╝██╔══██╗${RESET}"
    echo -e "${GREEN}  ██║     ██║     ██║   ██║██║   ██║█████╗  ██████╔╝${RESET}"
    echo -e "${GREEN}  ██║     ██║     ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗${RESET}"
    echo -e "${GREEN}  ╚██████╗███████╗╚██████╔╝ ╚████╔╝ ███████╗██║  ██║${RESET}"
    echo -e "${GREEN}   ╚═════╝╚══════╝ ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝${RESET}"
    echo ""
    echo -e "  ${DIM}Установщик ${GREEN}v1.0${RESET}  |  тгк: ${GREEN}@cloverUB${RESET}"
    echo -e "  ${GREEN}──────────────────────────────────────────────────────${RESET}"
    echo ""
}

divider() {
    echo -e "  ${DIM}──────────────────────────────────────────────────────${RESET}"
}

log_ok() {
    echo -e "  ${GREEN}✔${RESET}  $1"
}

log_err() {
    echo -e "  ${RED}✖${RESET}  $1"
}

spinner_start() {
    local label="$1"
    (
        local i=0
        tput civis 2>/dev/null
        while true; do
            printf "\r  ${GREEN}%s${RESET}  ${DIM}%s${RESET}   " \
                "${SPINNER_CHARS[$((i % 10))]}" "$label"
            i=$((i + 1))
            sleep 0.1
        done
    ) &
    SPINNER_PID=$!
}

spinner_stop() {
    if [ -n "$SPINNER_PID" ]; then
        kill "$SPINNER_PID" 2>/dev/null
        wait "$SPINNER_PID" 2>/dev/null
        SPINNER_PID=""
    fi
    printf "\r%-60s\r" " "
    tput cnorm 2>/dev/null
}

step() {
    local label="$1"
    local cmd="$2"
    spinner_start "$label"
    eval "$cmd" >> "$LOG_FILE" 2>&1
    local exit_code=$?
    spinner_stop
    if [ $exit_code -eq 0 ]; then
        log_ok "$label"
    else
        log_err "$label — ошибка (см. $LOG_FILE)"
        exit 1
    fi
}

step_live() {
    local label="$1"
    local cmd="$2"

    echo -e "\n  ${GREEN}┌─${RESET} ${WHITE}$label${RESET}"
    echo -e "  ${GREEN}│${RESET}"

    eval "$cmd" 2>&1 | while IFS= read -r line; do
        if echo "$line" | grep -qE '^\s+[A-Z]\s+(or|Or)\s+[A-Z]|^\s+[A-Z]\s*:'; then
            highlighted=$(echo "$line" | sed "s/\\b\([YNIODZyndiodz]\)\\b/\\x1b[1;32m\1\\x1b[0;2;32m/g")
            echo -e "  ${GREEN}│${RESET}  \033[2;32m${highlighted}${RESET}"
        elif echo "$line" | grep -qiE 'default action|keep your current|what do you want'; then
            echo -e "  ${GREEN}│${RESET}  ${YELLOW}$line${RESET}"
        else
            echo -e "  ${GREEN}│${RESET}  ${DIM}$line${RESET}"
        fi
    done
    local exit_code=${PIPESTATUS[0]}

    echo -e "  ${GREEN}│${RESET}"
    if [ $exit_code -eq 0 ]; then
        echo -e "  ${GREEN}└─${RESET} ${GREEN}✔  $label${RESET}\n"
    else
        echo -e "  ${GREEN}└─${RESET} ${RED}✖  $label — ошибка${RESET}\n"
        exit 1
    fi
}

install_requirements() {
    local req_file="$1"
    local total installed failed spin_pid exit_code pkg pkg_name
    total=$(grep -cE '^\s*[^#[:space:]]' "$req_file" 2>/dev/null || echo 0)
    installed=0
    failed=0

    echo -e "\n  ${GREEN}┌─${RESET} ${WHITE}Установка зависимостей${RESET}  ${DIM}(пакетов: $total)${RESET}"
    echo -e "  ${GREEN}│${RESET}"

    while IFS= read -r pkg || [ -n "$pkg" ]; do
        [[ -z "$pkg" || "$pkg" =~ ^[[:space:]]*# ]] && continue

        pkg_name=$(echo "$pkg" | sed 's/[>=<!;\[].*//' | tr -d '[:space:]')

        (
            local i=0
            tput civis 2>/dev/null
            while true; do
                printf "\r  ${GREEN}│${RESET}  ${GREEN}%s${RESET}  ${DIM}%-40s${RESET}   " \
                    "${SPINNER_CHARS[$((i % 10))]}" "$pkg_name"
                i=$((i + 1))
                sleep 0.08
            done
        ) &
        spin_pid=$!

        pip install "$pkg" --break-system-packages -q >> "$LOG_FILE" 2>&1
        exit_code=$?

        kill "$spin_pid" 2>/dev/null
        wait "$spin_pid" 2>/dev/null
        printf "\r%-70s\r" " "
        tput cnorm 2>/dev/null

        if [ $exit_code -eq 0 ]; then
            echo -e "  ${GREEN}│${RESET}  ${GREEN}✔${RESET}  ${DIM}$pkg_name${RESET}"
            installed=$((installed + 1))
        else
            echo -e "  ${GREEN}│${RESET}  ${RED}✖${RESET}  ${RED}$pkg_name — ошибка${RESET}"
            failed=$((failed + 1))
        fi

    done < "$req_file"

    echo -e "  ${GREEN}│${RESET}"
    if [ $failed -eq 0 ]; then
        echo -e "  ${GREEN}└─${RESET} ${GREEN}✔  Установлено: $installed / $total${RESET}\n"
    else
        echo -e "  ${GREEN}└─${RESET} ${YELLOW}⚠  Установлено: $installed / $total, ошибок: $failed${RESET}"
        echo -e "       ${DIM}Подробности: $LOG_FILE${RESET}\n"
        exit 1
    fi
}

banner

echo -e "  ${WHITE}Этот скрипт установит Clover и все зависимости.${RESET}"
echo -e "  ${DIM}Потребуется подключение к интернету.${RESET}"
echo ""
echo -ne "  ${GREEN}❯${RESET} Продолжить? (Enter / Ctrl+C для отмены) "
read -r

echo ""
divider
echo -e "\n  ${GREEN}[ 1 / 4 ]${RESET}  Обновление системы\n"

step_live "Разблокировка dpkg" "rm -f /data/data/com.termux/files/usr/var/lib/dpkg/lock* && dpkg --configure -a"
step_live "Обновление pkg"     "pkg update -y"
step_live "Обновление системы" "pkg upgrade -y -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'"
step_live "Установка софта"    "pkg install -y python ffmpeg dbus zbar"

echo ""
divider
echo -e "\n  ${GREEN}[ 2 / 4 ]${RESET}  Установка библиотек Python\n"

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    install_requirements "$SCRIPT_DIR/requirements.txt"
else
    log_err "Файл requirements.txt не найден в директории скрипта!"
    exit 1
fi

echo ""
divider
echo -e "\n  ${GREEN}[ 3 / 4 ]${RESET}  Настройка быстрого запуска\n"

MAIN_FILE="$SCRIPT_DIR/main.py"
BASHRC="$HOME/.bashrc"

sed -i '/alias [cC][lL][oO][vV][eE][rR]=/d' "$BASHRC" 2>/dev/null
sed -i '/^clover()/d'                         "$BASHRC" 2>/dev/null
sed -i '/^function clover /d'                 "$BASHRC" 2>/dev/null
sed -i '/# Clover —/d'                        "$BASHRC" 2>/dev/null

cat >> "$BASHRC" << BASHRC_EOF

_clover_run() { python "$MAIN_FILE" "\$@"; }
alias clover='_clover_run'
alias CLOVER='_clover_run'
alias Clover='_clover_run'
BASHRC_EOF

if grep -q 'shopt' "$BASHRC" 2>/dev/null; then
    true
else
    echo "shopt -s nocasematch 2>/dev/null || true" >> "$BASHRC"
fi

step "Создание команды 'clover'" "source $BASHRC"

echo ""
divider
echo -e "\n  ${GREEN}[ 4 / 4 ]${RESET}  Завершение\n"

log_ok "Проект расположен в: ${DIM}$SCRIPT_DIR${RESET}"
log_ok "Команда 'clover' прописана в ~/.bashrc"

echo ""
divider
echo -e "\n  ${GREEN}✨ Clover успешно установлен!${RESET}"
echo -e "  ${WHITE}Теперь вам не нужно заходить в папку с проектом.${RESET}"
echo -e "  ${WHITE}Просто введите в любом месте:${RESET} ${CYAN}clover${RESET}"
echo ""
echo -e "  ${YELLOW}Совет:${RESET} Если команда не подхватилась сразу,"
echo -e "         перезапустите Termux или введите: ${WHITE}source ~/.bashrc${RESET}"
echo ""
