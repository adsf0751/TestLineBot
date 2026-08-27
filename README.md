# LINE 遊戲服務

這是一個專屬於 LINE Bot 的遊戲服務專案。後端使用 Python、Flask 與 LINE Bot SDK，負責接收 LINE Webhook 訊息、解析遊戲指令、回覆遊戲結果，並把題目、答案、玩家暱稱、勝利宣言與遊戲紀錄寫入 `logs/`。

目前支援兩個遊戲：

- 算式拼圖
- 1A2B

## 專案結構

```text
.
├── app.py                         # LINE Webhook 入口
├── local_test.py                  # 本地單機測試入口
├── games/
│   ├── number_puzzle/             # 算式拼圖邏輯
│   └── one_a_two_b/               # 1A2B 邏輯
├── services/
│   ├── command_router.py          # 共用指令路由，不依賴 LINE SDK
│   └── line_users.py              # LINE 使用者暱稱、勝利宣言綁定與還原
├── tests/                         # 單元測試
└── logs/                          # runtime log 目錄
```

新增遊戲時，請在 `games/` 底下建立獨立資料夾，並把 LINE 指令分流集中接到 `services/command_router.py`，避免把遊戲邏輯直接寫進 `app.py`。

## 安裝套件

```powershell
pip install flask python-dotenv line-bot-sdk
```

如果只測試遊戲核心邏輯與 `local_test.py`，目前不需要額外套件；但要啟動 LINE Webhook 服務時，需要安裝上面三個套件。

## 環境變數

建立 `.env`：

```env
CHANNEL_ACCESS_TOKEN=你的 LINE Channel Access Token
CHANNEL_SECRET=你的 LINE Channel Secret
```

`.env` 已被 `.gitignore` 忽略，不應提交到版本控制。

## 本地單機測試

不接 LINE 時，可以直接使用本地測試入口：

```powershell
python local_test.py
```

進入互動模式後可以輸入：

```text
/user-本地測試
/userWin-這場我收下了
/banTime-5
/guessLimit-3
/guessBan-F
/-h
!-n
!-a
@-n
@-1234
@-l
@-a
exit
```

也可以用單次指令測試：

```powershell
python local_test.py /-h
python local_test.py /user-本地測試
python local_test.py /userWin-這場我收下了
python local_test.py /banTime-5
python local_test.py /guessLimit-3
python local_test.py /guessBan-F
```

本地模式會使用固定的模擬 LINE 使用者 ID：`local-user`。暱稱、勝利宣言、遊戲題目與操作紀錄仍會依正式流程寫入 `logs/`。

## 啟動 LINE Webhook 服務

```powershell
python app.py
```

服務預設監聽：

```text
0.0.0.0:5000
```

LINE Webhook URL 應指向：

```text
https://你的網域/webhook
```

## 指令列表

### 全域指令

| 指令 | 功能 |
| --- | --- |
| `/-h` | 列出目前所有可用的遊戲功能與指令 |
| `/user-暱稱` | 依照 LINE 使用者 ID 綁定暱稱，例如 `/user-小明` |
| `/userWin-勝利宣言` | 設定贏得遊戲時自動發布的玩家宣言，例如 `/userWin-這場我收下了` |
| `/banTime-分鐘` | 設定 1A2B 單一玩家暫停猜測時間，例如 `/banTime-5` |
| `/guessLimit-次數` | 設定 1A2B 單一玩家連續猜測上限，例如 `/guessLimit-3` |
| `/guessBan-T/F` | 設定 1A2B 連續猜測禁言開關，`T` 為啟用、`F` 為關閉，例如 `/guessBan-F` |

### 算式拼圖

| 指令 | 功能 |
| --- | --- |
| `!-n` | 產生新題目 |
| `!-a` | 查看當前題目的答案 |
| `!-h` | 查看算式拼圖可用指令 |

算式拼圖會隨機產生 3 個數字，並用 `+ - * / () ^` 產生一個沒有小數的目標值。系統會先自行驗算，確認算式正確後才會寫入 log 與回覆。

### 1A2B

| 指令 | 功能 |
| --- | --- |
| `@-n` | 開新遊戲 |
| `@-a` | 查看答案 |
| `@-l` | 查看當前回合猜測紀錄 |
| `@-h` | 查看 1A2B 可用指令 |
| `@-xxxx` | 猜測 4 位不重複半形數字，例如 `@-1234` |

1A2B 答案為 4 位不重複半形數字，可包含 `0`，因此 `@-0123` 是有效猜測。猜中答案後，該局會鎖定並拒絕後續猜測；玩家仍可使用 `@-l` 查看當前紀錄，直到使用 `@-n` 開新遊戲。

當 `/guessBan-T/F` 設為 `T` 時，若單一玩家連續猜測次數超過 `/guessLimit-次數` 設定值，系統會在該局暫停該玩家猜測 `/banTime-分鐘`。暫停期間其他玩家仍可繼續猜測；時間到後，只要有人觸發 1A2B 指令，系統會提示該玩家可以接續遊玩。若使用 `@-n` 開新遊戲，也會解除舊局的暫停猜測狀態並提示玩家可以接續遊玩。

`/guessBan-F` 會關閉連續猜測禁言，並清除目前所有 1A2B 對局中的禁言名單。`/guessBan-T` 會重新啟用連續猜測禁言，並從啟用當下開始重新計算連續猜測，不會用啟用前的猜測紀錄立即處罰玩家。

`/banTime-分鐘`、`/guessLimit-次數` 與 `/guessBan-T/F` 目前是執行期間設定；服務重啟後會回到預設值：暫停猜測 5 分鐘、連續猜測上限 3 次、連續猜測禁言啟用。

玩家使用 `/userWin-勝利宣言` 設定宣言後，若在 1A2B 猜中答案，系統會在勝利回覆中自動發布該玩家的勝利宣言。

## Log 說明

runtime log 會寫在 `logs/`，但實際 `.log` 檔案已被 `.gitignore` 忽略。

目前會產生：

- `logs/number_puzzle.log`：算式拼圖題目、目標值、算式答案與使用者資訊
- `logs/one_a_two_b.log`：1A2B 開局、猜測、查紀錄、看答案與使用者資訊
- `logs/line_users.log`：LINE 使用者 ID、暱稱與勝利宣言設定紀錄

LINE 使用者暱稱與勝利宣言會在服務啟動時從 `logs/line_users.log` 還原最新設定。

## 執行測試

```powershell
python -m unittest discover -s tests
```

語法檢查：

```powershell
python -m py_compile app.py local_test.py services\__init__.py services\line_users.py services\command_router.py games\__init__.py games\number_puzzle\__init__.py games\number_puzzle\game.py games\one_a_two_b\__init__.py games\one_a_two_b\game.py tests\test_number_puzzle.py tests\test_one_a_two_b.py tests\test_line_users.py tests\test_command_router.py
```

## 開發規範

- 所有文件必須使用自然、流暢的繁體中文撰寫。
- 各遊戲邏輯必須放在 `games/<game_name>/`。
- `app.py` 只負責 LINE Webhook、事件轉換與回覆傳送。
- 本地與 LINE 流程應共用 `services/command_router.py`，避免兩套指令邏輯不同步。
