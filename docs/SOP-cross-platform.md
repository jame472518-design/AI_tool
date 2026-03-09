# AI Code Review — Cross-Platform SOP

> ai-review CLI 跨平台安裝與使用標準作業流程
> 支援 Windows / macOS / Linux (Ubuntu)

---

## 目錄

1. [環境需求](#一環境需求)
2. [安裝 Ollama（本地 LLM）](#二安裝-ollama本地-llm)
3. [安裝 ai-review CLI](#三安裝-ai-review-cli)
4. [設定 LLM Provider](#四設定-llm-provider)
5. [安裝 Git Hooks](#五安裝-git-hooks)
6. [日常使用流程](#六日常使用流程)
7. [互動式 Commit 助手](#七互動式-commit-助手)
8. [使用情境](#八使用情境)
9. [更換/設定 LLM Model](#九更換設定-llm-model)
10. [常用指令速查表](#十常用指令速查表)
11. [疑難排解](#十一疑難排解)
12. [完整移除](#十二完整移除)

---

## 一、環境需求

| 項目 | 版本需求 | 說明 |
|------|----------|------|
| Python | >= 3.10 | 核心執行環境 |
| Git | 任意版本 | 版本管理 + hooks |
| pip | 任意版本 | Python 套件管理 |
| Ollama（選用） | 任意版本 | 本地 LLM 推理引擎 |

### Windows

```powershell
# 確認版本
python --version          # Python 3.10+
git --version
pip --version

# 若尚未安裝 Python
# 方式一：從 https://www.python.org/downloads/ 下載安裝（勾選 Add to PATH）
# 方式二：使用 Anaconda
#   下載 https://www.anaconda.com/download
#   安裝後開啟 Anaconda Prompt
```

> **Windows 注意事項：**
> - 建議使用 **Git Bash** 執行 ai-review（hooks 為 bash 腳本）
> - Anaconda 使用者：指令路徑在 `C:\Users\<USER>\anaconda3\Scripts\ai-review.exe`
> - CMD 中 commit message 請用**雙引號**：`git commit -m "[fix] xxx"`（單引號會出錯）

### macOS

```bash
# 確認版本
python3 --version         # Python 3.10+
git --version
pip3 --version

# 若尚未安裝
brew install python@3.12  # Homebrew
brew install git           # 通常 macOS 自帶
```

### Linux (Ubuntu/Debian)

```bash
# 確認版本
python3 --version         # Python 3.10+
git --version
pip3 --version

# 若尚未安裝
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

---

## 二、安裝 Ollama（本地 LLM）

Ollama 為本地 LLM 推理引擎。若使用 OpenAI 或企業 LLM，可跳過此節。

### Windows

1. 下載安裝檔：https://ollama.com/download/windows
2. 執行安裝程式，完成後會自動啟動 Ollama 服務
3. 開啟 CMD 或 PowerShell：

```powershell
# 確認安裝
ollama --version

# 下載模型（推薦 llama3.2，速度快、品質可接受）
ollama pull llama3.2

# 驗證模型
ollama list
```

### macOS

```bash
# 方式一：Homebrew
brew install ollama

# 方式二：官網下載
# https://ollama.com/download/mac

# 啟動服務
ollama serve &

# 下載模型
ollama pull llama3.2

# 驗證
ollama list
```

### Linux (Ubuntu)

```bash
# 一鍵安裝
curl -fsSL https://ollama.com/install.sh | sh

# 確認安裝
ollama --version

# 下載模型
ollama pull llama3.2

# 確認 Ollama 服務運行中
systemctl status ollama
# 若未啟動：
sudo systemctl start ollama
sudo systemctl enable ollama   # 開機自動啟動

# 驗證
ollama list
```

### 模型推薦

| 模型 | 大小 | 速度 | 品質 | 適用情境 |
|------|------|------|------|----------|
| `llama3.2` | 3.2B | ~8 秒 | 中 | 日常開發（推薦） |
| `llama3.1` | 8B | ~15 秒 | 中高 | 品質優先 |
| `codellama` | 7B | ~4 分鐘 | 高 | 需要時間但品質最好 |

---

## 三、安裝 ai-review CLI

### Windows

```powershell
# 方式一：從原始碼安裝（推薦）
git clone https://github.com/seen0722/ai-code-review.git
cd ai-code-review
pip install .

# 方式二：直接從 GitHub 安裝
pip install git+https://github.com/seen0722/ai-code-review.git

# 驗證安裝
ai-review --help

# 如果找不到指令，確認 Scripts 在 PATH 中：
# Anaconda: C:\Users\<USER>\anaconda3\Scripts\
# Python:   C:\Users\<USER>\AppData\Local\Programs\Python\Python3x\Scripts\
```

### macOS

```bash
# 方式一：從原始碼安裝（推薦）
git clone https://github.com/seen0722/ai-code-review.git
cd ai-code-review
python3 -m venv .venv
source .venv/bin/activate
pip install .

# 方式二：直接安裝
pip3 install git+https://github.com/seen0722/ai-code-review.git

# 驗證
ai-review --help
```

### Linux (Ubuntu)

```bash
# 方式一：從原始碼安裝（推薦）
git clone https://github.com/seen0722/ai-code-review.git
cd ai-code-review
python3 -m venv .venv
source .venv/bin/activate
pip install .

# 方式二：直接安裝
pip3 install git+https://github.com/seen0722/ai-code-review.git

# 驗證
ai-review --help
```

### 安裝驗證清單

```bash
ai-review --help              # 顯示所有指令
ai-review config show         # 顯示目前設定（應為空）
```

---

## 四、設定 LLM Provider

設定檔位置：`~/.config/ai-code-review/config.toml`

### 方案 A：本地 Ollama（推薦，無需外網）

```bash
ai-review config set provider default ollama
ai-review config set ollama base_url http://localhost:11434
ai-review config set ollama model llama3.2
ai-review config set ollama timeout 300    # 選用，預設 120 秒
```

### 方案 B：OpenAI（精確度最高）

```bash
# 設定 API Key 環境變數
# Windows PowerShell:
#   $env:OPENAI_API_KEY = "sk-xxx"
# Windows CMD:
#   set OPENAI_API_KEY=sk-xxx
# macOS / Linux:
#   export OPENAI_API_KEY="sk-xxx"

ai-review config set provider default openai
ai-review config set openai api_key_env OPENAI_API_KEY
ai-review config set openai model gpt-4o
```

### 方案 C：企業內部 LLM

```bash
ai-review config set provider default enterprise
ai-review config set enterprise base_url https://llm.internal.company.com
ai-review config set enterprise api_path /v1/chat/completions
ai-review config set enterprise model internal-codellama-70b
ai-review config set enterprise auth_type bearer
ai-review config set enterprise auth_token_env ENTERPRISE_LLM_KEY
```

### 驗證連線

```bash
ai-review health-check
# 預期輸出：
# Provider: ollama (llama3.2)
# Status: OK (...)
```

### 設定 Commit 相關

```bash
# 設定專案 ID（自動前綴 commit message）
ai-review config set commit project_id "PROJ-1"

# 初始化 commit 模板
ai-review config init-template

# 設定審查副檔名
ai-review config set review include_extensions "c,cpp,h,hpp,java,py,json"
```

---

## 五、安裝 Git Hooks

### 方式一：Template Hooks（推薦）

```bash
# 一次性全域設定
ai-review hook install --template

# 啟用 repo（clone 後直接執行，不需 git init）
cd /path/to/your-repo
ai-review hook enable              # 自動設定 config + 安裝 hooks
```

`hook enable` 會同時做兩件事：
1. 設定 `git config --local ai-review.enabled true`
2. 複製 4 個 hook 腳本到 `.git/hooks/`

### 方式二：Global Hooks

```bash
ai-review hook install --global

cd /path/to/your-repo
touch .ai-review                   # 有此檔案才會觸發 hooks
```

### 方式三：單一 Repo Hooks

```bash
cd /path/to/your-repo
ai-review hook install prepare-commit-msg
ai-review hook install commit-msg
touch .ai-review
```

### 批量管理多個 Repo

```bash
# 預覽目錄下所有 repo 狀態
ai-review hook enable --all /workspace --list
# 輸出：
#   camera-hal: disabled
#   audio-hal: enabled
#   kernel: disabled

# 批量啟用
ai-review hook enable --all /workspace

# 啟用指定 repo（不需 cd）
ai-review hook enable --path /workspace/camera-hal --path /workspace/kernel

# 批量停用
ai-review hook disable --all /workspace

# 停用指定 repo
ai-review hook disable --path /workspace/kernel
```

### 確認安裝狀態

```bash
ai-review hook status
```

### Windows 特別注意

> Hook 腳本為 bash 格式。Windows 使用者需確保：
> - 已安裝 **Git for Windows**（含 Git Bash）
> - Hook 腳本中的 ai-review 路徑使用 Unix 格式：`/c/Users/<USER>/anaconda3/Scripts/ai-review.exe`
> - 若自動偵測路徑失敗，可手動編輯 hook 腳本

### Hook 類型說明

| Hook | 觸發時機 | 功能 | 阻擋？ |
|------|---------|------|--------|
| `pre-commit` | `git commit` 最先 | AI 審查 staged 程式碼 | critical/error 時擋 |
| `prepare-commit-msg` | 編輯器開啟前 | 互動式選單（模板/優化/自動生成） | 否 |
| `commit-msg` | 編輯器關閉後 | 檢查 `[tag] description` 格式 | 格式錯時擋 |
| `pre-push` | `git push` 前 | AI 審查所有待推送 commits | critical/error 時擋 |

所有 hook 都帶 `--graceful`：LLM 連線失敗只警告，不阻擋操作。

---

## 六、日常使用流程

### 正常 Commit 流程

```bash
# 1. 修改程式碼
vim main.py

# 2. Stage 變更
git add main.py

# 3. Commit（觸發 hooks）
git commit
# → pre-commit: AI 審查程式碼（有嚴重問題會擋下）
# → prepare-commit-msg: 互動式選單出現
# → 選完後編輯器開啟，確認 message
# → commit-msg: 檢查格式
# → 完成 commit

# 4. Push（觸發 pre-push hook）
git push origin main
```

### 使用 -m 直接 Commit（跳過互動選單）

```bash
# Windows CMD 用雙引號
git commit -m "[fix] resolve camera crash"

# macOS / Linux 單雙引號皆可
git commit -m '[fix] resolve camera crash'
```

### 手動 Code Review

```bash
git add .
ai-review                        # Terminal 彩色輸出
ai-review --format markdown       # Markdown 格式（貼 Issue）
ai-review --format json           # JSON 格式（CI/CD 整合）
ai-review -v                      # Debug 模式
```

### 暫時跳過 Hooks

```bash
git commit --no-verify -m "[hotfix] emergency fix"
```

---

## 七、互動式 Commit 助手

執行 `git commit`（不帶 `-m`）時，會出現互動選單：

```
Commit Message Assistant
  1 Load template       - 載入模板
  2 LLM optimize        - AI 優化已有文字
  3 LLM auto-generate   - AI 自動生成
  s Skip                - 跳過，直接進編輯器
Choice [1/2/3/s]:
```

| 選項 | 功能 | 說明 |
|------|------|------|
| **1** | 載入模板 | 將 commit template 貼入編輯器 |
| **2** | AI 優化 | 輸入草稿文字，AI 優化格式與內容 |
| **3** | AI 自動生成 | 從 staged diff 全自動生成 commit message |
| **s** | 跳過 | 直接進入編輯器手動編寫 |

> 無論選擇哪個選項，最終都會進入編輯器讓你確認/修改後才 commit。

### 自訂模板

```bash
# 初始化模板到 config 目錄
ai-review config init-template

# 編輯模板
# Windows:
notepad %USERPROFILE%\.config\ai-code-review\commit-template.txt

# macOS / Linux:
vim ~/.config/ai-code-review/commit-template.txt
```

---

## 八、使用情境

### 情境一：個人開發者（一台機器，一個 repo）

```bash
# 安裝（一次性）
pip install .
ai-review config set provider default ollama
ai-review config set ollama model llama3.2
ai-review config init-template

# 啟用（在 repo 裡）
cd ~/my-project
ai-review hook enable

# 日常使用 — hooks 自動運作，不需額外操作
git add main.py
git commit                # ← 互動選單自動出現（選 1/2/3/s）
                          # ← 編輯器開啟確認 message
                          # ← commit-msg 自動檢查格式
git push                  # ← pre-push AI 自動審查
```

### 情境二：管理多個 Repo（BSP / Android 團隊）

```bash
# 一次性設定
ai-review hook install --template
ai-review config set commit project_id "BSP"

# 先看有哪些 repo
ai-review hook enable --all /workspace --list
# 輸出：
#   camera-hal: disabled
#   audio-hal: disabled
#   kernel: disabled
#   framework: disabled

# 全部啟用
ai-review hook enable --all /workspace
# 輸出：
#   Enabled: camera-hal
#   Enabled: audio-hal
#   ...
#   4/4 repos enabled.

# 只啟用特定幾個
ai-review hook enable --path /workspace/camera-hal --path /workspace/kernel

# 某個 repo 暫時不要 AI review
ai-review hook disable --path /workspace/kernel
```

### 情境三：團隊共用 LLM Server

```
開發機 A (Windows)  ──→
開發機 B (macOS)    ──→   LLM Server (192.168.1.100, GPU)
開發機 C (Linux)    ──→   Ollama + llama3.2
```

```bash
# Server 端（一次）
sudo systemctl edit ollama
# 加入 Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama

# 每台開發機（一次）
pip install .
ai-review config set provider default ollama
ai-review config set ollama base_url http://192.168.1.100:11434
ai-review config set ollama model llama3.2
ai-review health-check            # 驗證連線
```

### 情境四：Commit 時的互動選單

```bash
git add .
git commit    # 不加 -m，自動出現選單
```

```
Commit Message Assistant
  1 Load template       - 載入模板
  2 LLM optimize        - AI 優化已有文字
  3 LLM auto-generate   - AI 自動生成
  s Skip                - 跳過
```

| 選什麼 | 適合什麼時候 |
|--------|-------------|
| **1** | 忘了格式，載入模板填寫 |
| **2** | 已經有草稿，讓 AI 潤飾 |
| **3** | 懶得寫，AI 看 diff 自動生成 |
| **s** | 自己寫，不需要 AI |

> 選完後都會進編輯器讓你確認才 commit。

```bash
# 想跳過選單
git commit -m "[fix] quick fix"         # -m 直接跳過選單

# 想跳過所有 hooks
git commit --no-verify -m "[hotfix] emergency"
```

### 情境五：手動 Code Review（不透過 hooks）

```bash
git add kernel/drivers/gpu/panel.c
ai-review                              # terminal 彩色輸出
ai-review --format markdown             # 貼到 Issue / PR
ai-review --format json                 # CI/CD 整合
```

---

## 九、更換/設定 LLM Model

### 8.1 切換 Model（全平台通用）

```bash
# 查看目前設定的 model
ai-review config get ollama model

# 下載新模型
ollama pull llama3.2
ollama pull llama3.1
ollama pull codellama

# 查看已下載的模型
ollama list

# 切換 model
ai-review config set ollama model llama3.2

# 驗證
ai-review health-check
```

#### 模型比較

| 模型 | 參數量 | 回應速度 | 品質 | 適用情境 |
|------|--------|----------|------|----------|
| `llama3.2` | 3.2B | ~8 秒 | 中 | 日常開發（推薦） |
| `llama3.1` | 8B | ~15 秒 | 中高 | 品質優先 |
| `codellama` | 7B | ~4 分鐘 | 高 | 程式碼專用，品質最好 |
| `qwen2.5-coder` | 7B | ~20 秒 | 高 | 程式碼專用替代方案 |

> 小型 model（3B）速度快但可能產生誤報；大型 model（7B+）品質好但較慢。
> 依硬體和需求選擇適合的 model。

### 8.2 使用遠端 Ollama Server

當你有一台專門的 LLM Server（同網域），開發機可以透過 IP 連線使用：

```
┌──────────────────────┐     HTTP :11434     ┌──────────────────────┐
│  開發機 A (Windows)   │ ──────────────────→ │                      │
│  base_url=http://     │                     │   LLM Server         │
│   192.168.1.100:11434 │                     │   (Ubuntu + GPU)     │
├──────────────────────┤                     │                      │
│  開發機 B (macOS)     │ ──────────────────→ │   Ollama + llama3.2  │
│  base_url=http://     │                     │   OLLAMA_HOST=0.0.0.0│
│   192.168.1.100:11434 │                     │                      │
├──────────────────────┤                     │   IP: 192.168.1.100  │
│  開發機 C (Linux)     │ ──────────────────→ │                      │
│  base_url=http://     │                     └──────────────────────┘
│   192.168.1.100:11434 │
└──────────────────────┘
```

#### Client 端設定（開發機，全平台通用）

只需一行指令，將 `base_url` 改為 Server IP：

```bash
# 設定遠端 server（替換為實際 IP）
ai-review config set ollama base_url http://192.168.1.100:11434

# 驗證連線
ai-review health-check
# 預期輸出：
# Provider: ollama (llama3.2)
# Status: OK (Connected)

# 如果要切回本地
ai-review config set ollama base_url http://localhost:11434
```

#### Server 端設定（LLM Server）

Ollama 預設只監聽 `localhost`，需改為監聽所有網卡 (`0.0.0.0`)：

**Linux (Ubuntu) — systemd 方式（推薦）**

```bash
# 編輯 Ollama service
sudo systemctl edit ollama

# 在編輯器中加入：
[Service]
Environment="OLLAMA_HOST=0.0.0.0"

# 重啟服務
sudo systemctl daemon-reload
sudo systemctl restart ollama

# 確認監聽
ss -tlnp | grep 11434
# 應顯示 0.0.0.0:11434
```

**Linux (Ubuntu) — 環境變數方式**

```bash
# 加入 ~/.bashrc 或 /etc/environment
export OLLAMA_HOST=0.0.0.0

# 重啟 Ollama
sudo systemctl restart ollama
```

**Windows**

```powershell
# 方式一：系統環境變數（永久）
# 設定 > 系統 > 進階系統設定 > 環境變數
# 新增系統變數：OLLAMA_HOST = 0.0.0.0
# 重啟 Ollama

# 方式二：PowerShell（暫時）
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
```

**macOS**

```bash
# 設定環境變數
launchctl setenv OLLAMA_HOST "0.0.0.0"

# 重啟 Ollama（從應用程式關閉後重開）
# 或終端啟動：
OLLAMA_HOST=0.0.0.0 ollama serve
```

#### 防火牆設定

```bash
# Linux (UFW)
sudo ufw allow 11434/tcp

# Windows
# 設定 > Windows 防火牆 > 進階設定 > 輸入規則 > 新增規則
# 類型: Port, TCP, 11434, 允許連線

# macOS（通常不需要，系統會提示允許）
```

#### 驗證遠端連線

```bash
# 從開發機測試（替換為 Server IP）
curl http://192.168.1.100:11434/api/tags

# 或直接用 ai-review
ai-review config set ollama base_url http://192.168.1.100:11434
ai-review health-check
```

### 8.3 切換 Provider

除了 Ollama，也可以隨時切換到其他 Provider：

```bash
# 查看目前 provider
ai-review config get provider default

# 切換到 OpenAI
ai-review config set provider default openai

# 切換回 Ollama
ai-review config set provider default ollama

# 臨時使用不同 provider（不改設定）
ai-review --provider openai --model gpt-4o
```

---

## 十、常用指令速查表

### 設定相關

| 指令 | 說明 |
|------|------|
| `ai-review config show` | 顯示所有設定 |
| `ai-review config show ollama` | 顯示特定 section |
| `ai-review config get provider default` | 取得單一設定值 |
| `ai-review config set <section> <key> <value>` | 設定值 |
| `ai-review config init-template` | 初始化 commit 模板 |

### Hook 管理

| 指令 | 說明 |
|------|------|
| `ai-review hook install --template` | 安裝 template hooks（推薦） |
| `ai-review hook install --global` | 安裝 global hooks |
| `ai-review hook install commit-msg` | 安裝單一 repo hook |
| `ai-review hook uninstall --template` | 移除 template hooks |
| `ai-review hook status` | 查看 hook 安裝狀態 |
| `ai-review hook enable` | 啟用當前 repo（自動安裝 hooks） |
| `ai-review hook enable --path <dir>` | 啟用指定 repo（可重複） |
| `ai-review hook enable --all <dir>` | 批量啟用目錄下所有 repo |
| `ai-review hook enable --all <dir> --list` | 預覽所有 repo 狀態 |
| `ai-review hook disable` | 停用當前 repo |
| `ai-review hook disable --path <dir>` | 停用指定 repo |
| `ai-review hook disable --all <dir>` | 批量停用 |

### 診斷

| 指令 | 說明 |
|------|------|
| `ai-review health-check` | 測試 LLM 連線 |
| `ai-review -v` | Debug 模式審查 |

---

## 十一、疑難排解

### 全平台通用

| 問題 | 解法 |
|------|------|
| `ai-review: command not found` | 確認 pip Scripts 目錄在 PATH 中 |
| `health-check` 失敗 | 確認 Ollama 服務運行中：`ollama list` |
| LLM 回應太慢 | 換小模型：`ai-review config set ollama model llama3.2` |
| Timeout 錯誤 | 加大 timeout：`ai-review config set ollama timeout 300` |
| Hook 不觸發 | 確認：`ai-review hook status` + `hook enable` |
| Commit message 格式被擋 | 格式須為 `[tag] description`，例如 `[fix] resolve crash` |

### Windows 專屬

| 問題 | 解法 |
|------|------|
| 單引號 commit 失敗 | 用雙引號：`git commit -m "[fix] xxx"` |
| Hook 中找不到 ai-review | 用完整路徑：`/c/Users/<USER>/anaconda3/Scripts/ai-review.exe` |
| 中文亂碼 | 確認終端 UTF-8：`chcp 65001` |
| pip install 失敗（檔案被鎖） | 關閉所有使用 ai-review 的終端後重試 |

### macOS 專屬

| 問題 | 解法 |
|------|------|
| `python3` 找不到 | `brew install python@3.12` |
| Ollama 未啟動 | `ollama serve &` 或從應用程式啟動 |

### Linux 專屬

| 問題 | 解法 |
|------|------|
| Ollama 服務未運行 | `sudo systemctl start ollama` |
| 權限不足 | `pip install --user .` 或使用 venv |
| Hook 無執行權限 | `chmod +x .git/hooks/*` |

---

## 十二、完整移除

### Windows

```powershell
# 移除 hooks
ai-review hook uninstall --template
# 或
ai-review hook uninstall --global

# 移除套件
pip uninstall ai-code-review

# 移除設定
rmdir /s /q %USERPROFILE%\.config\ai-code-review

# 移除 Ollama（從「設定 > 應用程式」解除安裝）
```

### macOS

```bash
ai-review hook uninstall --template
pip3 uninstall ai-code-review
rm -rf ~/.config/ai-code-review

# 移除 Ollama
brew uninstall ollama
# 或刪除 Ollama.app
```

### Linux

```bash
ai-review hook uninstall --template
pip3 uninstall ai-code-review
rm -rf ~/.config/ai-code-review

# 移除 Ollama
sudo systemctl stop ollama
sudo systemctl disable ollama
sudo rm /usr/local/bin/ollama
sudo rm -rf /usr/share/ollama
sudo userdel ollama
```

---

## 附錄：快速安裝腳本

### macOS / Linux

存為 `setup-ai-review.sh`：

```bash
#!/usr/bin/env bash
set -e
REPO_URL="${AI_REVIEW_REPO:-https://github.com/seen0722/ai-code-review.git}"
MODEL="${OLLAMA_MODEL:-llama3.2}"

echo "=== AI Code Review Setup ==="

# 安裝 ai-review
git clone "$REPO_URL" ~/ai-code-review
cd ~/ai-code-review
python3 -m venv .venv
source .venv/bin/activate
pip install .

# 設定 Ollama
ai-review config set provider default ollama
ai-review config set ollama base_url "${OLLAMA_URL:-http://localhost:11434}"
ai-review config set ollama model "$MODEL"
ai-review config set ollama timeout 300

# 初始化模板
ai-review config init-template

# 安裝 hooks
ai-review hook install --template

# 驗證
ai-review health-check

echo ""
echo "=== Setup Complete ==="
echo "啟用 repo:  cd /your/repo && ai-review hook enable"
echo "跳過 hook:  git commit --no-verify"
```

```bash
# 使用
chmod +x setup-ai-review.sh
./setup-ai-review.sh
```

### Windows (PowerShell)

存為 `setup-ai-review.ps1`：

```powershell
$ErrorActionPreference = "Stop"
$REPO_URL = if ($env:AI_REVIEW_REPO) { $env:AI_REVIEW_REPO } else { "https://github.com/seen0722/ai-code-review.git" }

Write-Host "=== AI Code Review Setup ==="

git clone $REPO_URL "$HOME\ai-code-review"
Set-Location "$HOME\ai-code-review"
pip install .

ai-review config set provider default ollama
ai-review config set ollama base_url "http://localhost:11434"
ai-review config set ollama model "llama3.2"
ai-review config set ollama timeout 300
ai-review config init-template
ai-review hook install --template
ai-review health-check

Write-Host ""
Write-Host "=== Setup Complete ==="
Write-Host "Enable repo:  cd /your/repo; ai-review hook enable"
```

```powershell
# 使用
.\setup-ai-review.ps1
```
