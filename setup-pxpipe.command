#!/bin/zsh
# pxpipe 一鍵安裝(執行一次後可刪除此檔;不要 commit 進 repo)
set -e

echo "=== 檢查 Node.js / npm ==="
if ! command -v npm >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "找不到 npm,用 Homebrew 安裝 Node.js..."
    brew install node
  else
    echo "錯誤:沒有 npm 也沒有 Homebrew。請先到 https://nodejs.org 安裝 Node.js 再重跑。"
    exit 1
  fi
fi
echo "npm 版本:$(npm -v)"

echo "=== 全域安裝 pxpipe-proxy ==="
npm install -g pxpipe-proxy

echo "=== 寫入 shell 別名 ==="
ZSHRC="$HOME/.zshrc"
if ! grep -q "ANTHROPIC_BASE_URL=http://127.0.0.1:47821" "$ZSHRC" 2>/dev/null; then
  cat >> "$ZSHRC" <<'EOF'

# pxpipe — Claude Code token 壓縮代理
alias pxpipe-start='nohup pxpipe-proxy >/tmp/pxpipe.log 2>&1 & sleep 1 && echo "pxpipe 已啟動,儀表板: http://127.0.0.1:47821"'
alias pxpipe-stop='pkill -f pxpipe-proxy && echo "pxpipe 已停止"'
alias claudex='ANTHROPIC_BASE_URL=http://127.0.0.1:47821 claude'
EOF
  echo "別名已加入 ~/.zshrc"
else
  echo "別名已存在,略過"
fi

echo ""
echo "=== 安裝完成 ==="
echo "使用方式(開新終端機視窗後):"
echo "  pxpipe-start   # 啟動代理(每次開機後跑一次)"
echo "  claudex        # 用省 token 模式啟動 Claude Code"
echo "  claude         # 原本的用法不受影響"
echo "  pxpipe-stop    # 停止代理"
echo "儀表板: http://127.0.0.1:47821"
echo ""
echo "提醒:此檔案(setup-pxpipe.command)用完可刪,不要 git add。"
