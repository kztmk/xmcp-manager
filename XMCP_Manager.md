# XMCP Manager 実装仕様書

X API x MCP Client 連携 / 複数 X アカウント切り替え対応 GUI 管理アプリ

---

## 1. 目的

XMCP Manager は、非エンジニアのユーザーが Claude Desktop や Codex Desktop などの MCP client から X を操作できるように、ローカルの `xmcp` MCP サーバーを管理するデスクトップ GUI アプリである。

この文書は開発者向けの実装仕様書であり、実装責務、データ境界、外部コンポーネントとの接続、配布形式、検証観点を定義する。

## 2. スコープ

### 2-1. 実現すること

- X アカウントごとの API Credentials を OS キーチェーンへ保存する
- X アカウントごとの Account Metadata を OS 標準のユーザーデータディレクトリへ保存する
- X アカウントごとに Tool Allowlist を設定する
- 選択中の X アカウントで `xmcp` サーバーを起動・停止する
- Claude Desktop と Codex Desktop の MCP client 設定を更新する
- Windows と macOS で OS 標準の単体アプリ体験として配布する

### 2-2. 初期スコープ外

- `xmcp` 本体の改造
- OAuth callback や OAuth access token の永続化管理
- Linux の正式サポート
- 複数 Developer App を同一 X アカウントへ登録する機能
- OpenAPI spec のローカルキャッシュ

## 3. コンポーネント境界

### 3-1. XMCP Manager

XMCP Manager は以下を担当する。

- GUI
- X アカウント一覧の管理
- API Credentials の保存・取得
- `xmcp` プロセスの起動・停止
- `xmcp` 起動時の環境変数生成
- MCP client 設定ファイルの更新
- 起動状態、認証待ち、接続可能状態、エラーの表示

### 3-2. xmcp

`xmcp` は内包された外部コンポーネントとして扱う。XMCP Manager は `xmcp/server.py` を同梱して起動するが、`xmcp` の内部実装はこのプロジェクトの所有物として扱わない。

`xmcp` は以下を担当する。

- X API OpenAPI spec の取得
- OAuth1 consent フロー
- OAuth callback の待ち受け
- OAuth access token のプロセス内保持
- X API request への OAuth1 signing
- HTTP MCP endpoint の公開

## 4. システム構成

```text
┌─────────────────────────────────────────────┐
│ XMCP Manager GUI                            │
│ Python / CustomTkinter                      │
│                                             │
│ - X Account selection                       │
│ - Account Metadata management               │
│ - API Credentials keychain storage          │
│ - Tool Allowlist configuration              │
│ - xmcp process management                   │
│ - MCP client config update                  │
└──────────────┬──────────────────────────────┘
               │ subprocess + environment
               ▼
┌─────────────────────────────────────────────┐
│ Embedded external xmcp server.py            │
│ HTTP MCP endpoint                           │
│ Default: http://127.0.0.1:8000/mcp          │
│ OAuth1 callback default: 127.0.0.1:8976     │
└──────────────┬──────────────────────────────┘
               │ HTTP MCP
               ▼
┌─────────────────────────────────────────────┐
│ MCP Client                                  │
│ Claude Desktop / Codex Desktop             │
│ Natural-language X operations via MCP       │
└─────────────────────────────────────────────┘
```

## 5. X アカウントと認証情報

### 5-1. X アカウントの単位

XMCP Manager の「アカウント」は X のユーザーアカウントを指す。

X API を使用するため、ユーザーは対象の X アカウントで X Developer Portal にアクセスし、Developer App を作成して、その App の API Credentials を取得する。

初期仕様では、1 つの X アカウントにつき 1 つの API Credentials セットだけを登録できる。同一 X アカウントに複数 Developer App / API Credentials セットを登録する機能は持たない。

### 5-2. 初期 UI で入力する API Credentials

初期 UI では以下の 3 項目を入力する。

| UI 項目 | `xmcp` 環境変数 |
|---|---|
| API Key | `X_OAUTH_CONSUMER_KEY` |
| API Key Secret | `X_OAUTH_CONSUMER_SECRET` |
| Bearer Token | `X_BEARER_TOKEN` |

内部の credential 保存形式は、将来の追加項目に耐えるよう schema version を持つ。

### 5-3. 保存先

| データ | 保存先 | 秘密情報 |
|---|---|---|
| Account Metadata | OS 標準のユーザーデータディレクトリ | No |
| API Credentials | OS キーチェーン | Yes |

Account Metadata には `@handle`、表示名、最終使用日時、Tool Allowlist、詳細設定などの秘密でない情報だけを保存する。API Key、API Key Secret、Bearer Token は API Credentials として扱い、JSON ファイルへ保存しない。

Account Metadata と API Credentials の両方に schema version を持たせる。

OS 標準ユーザーデータディレクトリの app name と author/vendor はどちらも `XMCP Manager` とする。ユーザーデータディレクトリ内の構成は以下とする。

```text
<AppData>/XMCP Manager/
├── app_settings.json
├── accounts.json
├── tool_catalog.json
└── backups/
    ├── claude-desktop/
    └── codex-desktop/
```

### 5-4. App Settings schema

アプリ全体設定は OS 標準のユーザーデータディレクトリへ保存する。MCP endpoint と、前回選択した MCP client 設定更新対象を保持する。

初回は `selectedMcpClients` を空配列にし、ユーザーが Claude Desktop / Codex Desktop のどちらを更新するか明示選択する。選択後は次回の初期値として復元する。

```json
{
  "version": 1,
  "mcpHost": "127.0.0.1",
  "mcpPort": 8000,
  "oauthCallbackHost": "127.0.0.1",
  "oauthCallbackPort": 8976,
  "oauthCallbackPath": "/oauth/callback",
  "selectedMcpClients": [],
  "clientOverwriteAcceptedUrls": {
    "claude-desktop": null,
    "codex-desktop": null
  },
  "storeValidation": {
    "version": 1,
    "appVersion": null,
    "externalConfigWritable": {
      "claude-desktop": null,
      "codex-desktop": null
    },
    "loopbackAvailable": null,
    "credentialStoreAvailable": null,
    "userDataWritable": null,
    "validatedAt": null
  },
  "broadWritePresetWarningAccepted": false,
  "fullAccessWarningAccepted": false
}
```

### 5-5. Account Metadata schema

Account Metadata の内部 ID は `uuid` とする。X の `@handle` は変更される可能性があるため、保存キーやキーチェーン参照の主キーにはしない。

```json
{
  "version": 1,
  "accounts": [
    {
      "id": "0f4d9f5c-8b6f-4a3e-9e9e-0d9f2f8c1a11",
      "handle": "@example",
      "displayName": "Example",
      "lastUsedAt": "2026-06-24T00:00:00Z",
      "toolAllowlistPreset": "broad_write",
      "toolAllowlist": ["getUsersMe", "getUsersByUsername"],
      "settings": {}
    }
  ]
}
```

### 5-6. API Credentials schema

API Credentials は OS キーチェーンに保存する。キーチェーン service name は `XMCP Manager` とし、キーチェーン上の account name は Account Metadata の `id` を使う。

```json
{
  "version": 1,
  "consumerKey": "...",
  "consumerSecret": "...",
  "bearerToken": "..."
}
```

OS キーチェーンへの保存に失敗した場合、XMCP Manager は保存失敗としてユーザーに案内し、JSON や暗号化ファイルへフォールバック保存しない。

Account Metadata が存在するが OS キーチェーンから API Credentials を読み出せない場合、アカウントは削除せず `credentials missing` として表示し、ユーザーに再入力を求める。

アカウント削除時は Account Metadata と OS キーチェーン上の API Credentials の両方を削除する。キーチェーン削除に失敗した場合は警告を表示する。

GUI では保存済み API Credentials を平文で再表示しない。保存済み項目はマスク表示し、変更する項目だけ再入力できるようにする。

編集時の空欄は既存値維持として扱う。新規登録時は全必須項目を入力しなければ保存できない。

保存時は X API への実疎通確認を行わず、必須項目と形式だけを確認する。実疎通は `xmcp` サーバー起動時に確認する。

形式チェックでは、前後空白を trim し、空欄と改行混入を拒否する。X API token 形式を正規表現で厳密には固定しない。

起動時の credentials 確認では、OS キーチェーンから secret JSON を読み出して JSON parse と version 確認を行う。ただし値は長時間メモリ保持しない。

credentials 状態は以下に分類する。

| 状態 | 意味 |
|---|---|
| `ok` | キーチェーンから読み出し、schema と必須値を確認できた |
| `missing` | 対応するキーチェーン項目が存在しない |
| `invalid` | JSON 破損、schema version 不一致、必須値欠落など |
| `inaccessible` | キーチェーン権限拒否、ロック、バックエンドエラーなど |

Account Metadata が読み込めない場合、キーチェーン上の API Credentials は自動操作しない。metadata 復旧を優先し、service name に属する credentials の一括削除や再生成は行わない。

## 6. Tool Allowlist

`xmcp` は `X_API_TOOL_ALLOWLIST` によって公開する tool を制限できる。XMCP Manager はこの機能を X アカウントごとの設定として扱う。

初期 UI はプリセット中心とし、詳細設定で `xmcp` の tool 名を直接編集できるようにする。具体的な tool 名リストは、実装時に同梱する `xmcp` の tool list から生成・管理する。仕様書ではプリセットの安全方針を定義し、全 tool 名を固定列挙しない。

想定プリセット:

| プリセット | 目的 |
|---|---|
| 読み取りのみ | プロフィール、投稿、検索などの参照操作を許可する |
| 広範な書き込み操作 | 投稿、削除、DM、フォロー、ブロックなど主要な X 操作を許可する |
| フルアクセス | `X_API_TOOL_ALLOWLIST` を未設定または空にし、`xmcp` が公開する全 tool を許可する |
| カスタム | 生の tool 名リストを使用する |

初期デフォルトは `広範な書き込み操作` とする。

`広範な書き込み操作` は公開操作、第三者への操作、削除操作、X API の従量課金に影響する可能性がある。初回サーバー起動時にはブロッキング確認を表示し、ユーザーが明示的に同意しない限り起動しない。

この確認済み状態はアプリ全体設定に保存し、一度同意された後は別の X アカウントでも再表示しない。

`フルアクセス` は `xmcp` に将来追加される未知の tool も自動的に公開するため、`広範な書き込み操作` とは別のブロッキング確認を表示する。ユーザーが明示的に同意しない限り起動しない。

`フルアクセス` の確認済み状態もアプリ全体設定に保存し、一度同意された後は別の X アカウントでも再表示しない。

プリセットから最終的な `X_API_TOOL_ALLOWLIST` 値を生成し、`xmcp` 起動時の環境変数に設定する。

プリセット生成ルール:

| プリセット | 生成ルール |
|---|---|
| 読み取りのみ | Tool Catalog 上の `riskLevel = read` の tool だけを含める |
| 広範な書き込み操作 | Tool Catalog 上の `read`, `write`, `destructive`, `sensitive` の tool を含める。unknown / uncategorized tool は含めない |
| フルアクセス | `X_API_TOOL_ALLOWLIST` を未設定または空にする |
| カスタム | ユーザーが選択した tool 名をそのまま allowlist 化する |

`カスタム` では unknown / uncategorized tool を選択できる。ただし起動前にブロッキング確認を表示し、ユーザーが明示的に同意しない限り起動しない。この確認済み状態は保存せず、該当 tool が含まれる起動ごとに毎回確認する。

### 6-1. Tool Catalog

XMCP Manager は `xmcp` tool 名を管理する Tool Catalog を持つ。Tool Catalog は Tool Allowlist の UI 表示、プリセット生成、カスタム allowlist 検証に使用する。

Tool Catalog は tool 名、UI グルーピング、操作種別、risk level を持つ。`category` は UI グルーピングに使い、`actionType` はプリセット生成とリスク判定に使う。

`riskLevel` は以下の値を使う。

| riskLevel | 意味 |
|---|---|
| `read` | 参照系操作 |
| `write` | 作成・更新などの書き込み操作 |
| `destructive` | 削除、ブロックなど取り消しや影響が大きい操作 |
| `sensitive` | DM などプライバシー性が高い操作 |
| `unknown` | 自動分類または override で分類できない操作 |

`actionType` は X の対象リソースに沿って分類する。例: `post`, `dm`, `follow`, `block`, `list`, `media`, `search`, `profile`, `analytics`, `other`。

```json
{
  "version": 1,
  "source": "bundled",
  "generatedAt": "2026-06-24T00:00:00Z",
  "xmcpRevision": "master",
  "tools": [
    {
      "name": "createPosts",
      "category": "Posts",
      "actionType": "post",
      "riskLevel": "write",
      "description": "Create a post"
    }
  ]
}
```

初期配布物には、同梱する `xmcp` の tool list から開発時生成スクリプトで作成した static catalog JSON を `src/xmcp_manager/resources/tool_catalog.json` として含める。アプリ起動時に毎回自動更新しない。

開発時生成スクリプトは repo root の `scripts/generate_tool_catalog.py` とする。tool 名から `category`、`actionType`、`riskLevel` を自動推定し、`src/xmcp_manager/resources/tool_catalog_overrides.json` で手動補正する。

vendored `xmcp` 更新用に repo root の `scripts/update_vendored_xmcp.py` を用意する。このスクリプトは `--revision <commit-sha>` を必須引数とし、full 40-character commit SHA だけを受け付ける。`master` 最新や短縮 SHA は使用しない。

`update_vendored_xmcp.py` は指定 revision から `xmcp/server.py` を取得し、`VENDORED_XMCP_REVISION` を更新し、Tool Catalog 再生成と generation check まで自動実行する。

vendored 更新時の Tool Catalog 再生成で network 失敗または OpenAPI spec 取得失敗が発生した場合、スクリプトは失敗扱いにする。古い catalog を使って続行しない。

override file に存在しない新規 tool が生成された場合、生成スクリプトは warning を出すが生成は成功させる。自動推定で分類できない tool は `actionType: "other"`、`riskLevel: "unknown"` として catalog に含める。

ユーザーはアプリ内の手動 refresh で Tool Catalog を更新できる。手動 refresh で取得した catalog は OS 標準のユーザーデータディレクトリに保存し、同梱 static catalog より優先して使用する。

手動 refresh は `https://api.x.com/2/openapi.json` を認証なしで取得する。timeout は 30 秒とし、`xmcp` の現行 OpenAPI spec 取得 timeout と揃える。

refresh に失敗した場合、既存の有効 catalog を維持して警告を表示する。最後に成功したユーザー catalog があればそれを使い、なければ同梱 static catalog を使う。

Tool Catalog は allowlist UI と起動前検証に使う時点の tool 情報であり、`xmcp` がサーバー起動時に取得する OpenAPI spec と完全一致することは保証しない。`xmcp` を改造しない初期仕様では、Catalog refresh 時点と `xmcp` 起動時点の差分を許容する。

`カスタム` preset では、サーバー起動前に Tool Catalog を使って tool 名を検証する。無効な tool 名または削除済み tool 名が含まれる場合、XMCP Manager は起動を止め、ユーザーに修正を求める。

## 7. xmcp 起動仕様

### 7-1. 起動方法

XMCP Manager は同梱した `xmcp/server.py` をサブプロセスとして起動する。

```bash
python server.py
```

PyInstaller で配布する場合も、`xmcp/server.py` と `xmcp` の依存関係をアプリに同梱する。

### 7-2. 必須環境変数

`xmcp` の現行仕様では以下が必須である。

| 環境変数 | 値 |
|---|---|
| `X_OAUTH_CONSUMER_KEY` | API Credentials から取得 |
| `X_OAUTH_CONSUMER_SECRET` | API Credentials から取得 |
| `X_BEARER_TOKEN` | API Credentials から取得 |

### 7-3. XMCP Manager が設定する環境変数

| 環境変数 | 初期値 | 説明 |
|---|---|---|
| `MCP_HOST` | `127.0.0.1` | MCP server bind host |
| `MCP_PORT` | `8000` | MCP server port |
| `X_API_TOOL_ALLOWLIST` | アカウント設定由来 | 公開 tool の制限 |
| `X_OAUTH_CALLBACK_HOST` | `127.0.0.1` | OAuth callback host |
| `X_OAUTH_CALLBACK_PORT` | `8976` | OAuth callback port |
| `X_OAUTH_CALLBACK_PATH` | `/oauth/callback` | OAuth callback path |
| `X_OAUTH_CALLBACK_TIMEOUT` | `300` | OAuth callback timeout seconds |

`MCP_PORT` はデフォルトを `8000` とする。詳細設定で変更可能にし、MCP client 設定の URL と `xmcp` 起動 env を同じアプリ全体設定値から生成する。変更時は、MCP client 設定更新が必要であることを案内する。

OAuth callback は host を `127.0.0.1`、path を `/oauth/callback` に固定する。初期 UI では callback port のみ詳細設定で変更可能にする。callback port もアプリ全体設定とする。

callback port を変更する場合、GUI は `http://127.0.0.1:<port>/oauth/callback` を表示し、コピー可能にする。保存時には、X Developer Portal 側の Callback URI 更新が必要であることをブロッキング確認する。

MCP port と callback port はどちらも `1024` から `65535` の範囲だけ許可する。

### 7-4. オンライン前提

`xmcp` は起動時に X API OpenAPI spec を取得する。したがって、サーバー起動にはネットワーク接続と X API 側への到達性が必要である。

起動失敗時、XMCP Manager は単なる起動失敗ではなく、可能な限り以下を区別して GUI に表示する。

- API Credentials 不足
- OAuth 認証待ちまたは timeout
- OpenAPI spec 取得失敗
- X API 認証エラー
- ポート競合
- その他のプロセス終了

## 8. アプリ起動時ロード

XMCP Manager の起動時ロード順は以下とする。

1. App Settings を読み込む
2. Account Metadata を読み込む
3. Tool Catalog を読み込む。ユーザー catalog があれば優先し、なければ同梱 catalog を使う
4. 各 account の credentials 状態をキーチェーンで確認する
5. `selectedMcpClients` に入っている MCP client の設定 URL を必要に応じて確認する
6. 同じ endpoint の管理外プロセスを検出する

App Settings または Account Metadata の JSON が壊れている場合、アプリ自体は起動するが、該当データは読み込まない。壊れたファイルを自動上書きせず、recovery 案内を表示する。

ユーザー Tool Catalog が壊れている場合は同梱 Tool Catalog に fallback する。同梱 Tool Catalog も読み込めない場合は、Tool Allowlist 機能を disabled にし、配布物破損または再インストールが必要であることを表示する。Tool Catalog 破損時に自動 refresh は行わない。

recovery 案内では、対象ファイルのパス、推奨リネーム先例、手動復元手順を表示する。推奨リネーム先は `accounts.json.broken-YYYYMMDD-HHMMSS` のような timestamp 付き名称とする。

壊れたファイルの中身は GUI に表示しない。

recovery 案内と backup 案内では、対象フォルダを OS 標準ファイルマネージャで開くボタンを提供する。この操作は共通ユーティリティとして実装する。

## 9. アカウント切り替え

アカウント切り替えはサーバー再起動方式を採用する。

1. 既存の `xmcp` プロセスを停止する
2. 選択された X アカウントの API Credentials と Tool Allowlist を読み込む
3. 環境変数を生成する
4. 同一または設定済みポートで `xmcp` を再起動する

切り替え時、MCP client から見ると MCP 接続は一時的に切断される。数秒の切断は仕様として許容し、再接続後に選択中の X アカウントで動作すればよい。

## 10. プロセス管理

XMCP Manager が停止対象にするのは、自身が現在のセッションで起動した `xmcp` プロセスだけである。同じ port を使う既存プロセスや、管理外の `xmcp` らしいプロセスは自動停止しない。

同じ MCP endpoint に管理外プロセスが応答している場合、GUI では管理外プロセスとして表示する。MCP client 設定更新は許可するが、停止操作は提供しない。

管理外プロセスが同じ port を使っている状態で「このアカウントで起動」を押した場合、XMCP Manager は起動を止め、ポート競合として原因と手動停止方法を案内する。管理外プロセスを自動停止したり、別 port を自動選択したりしない。

アプリ終了時に管理対象 `xmcp` プロセスが起動中の場合、終了確認を表示する。既定の選択は `xmcp` も停止する。ユーザーが明示的に「起動したままにする」を選んだ場合だけ、`xmcp` を残してアプリを終了する。

前回「起動したままにする」を選んだ `xmcp` が次回起動時に残っていても、XMCP Manager はそれを管理対象として取り込まない。管理外プロセスとして検出し、停止操作は提供しない。

管理対象プロセスの停止は `terminate()` を行い、5 秒待っても終了しない場合は `kill()` する。

## 11. Server State

GUI では Server State を以下の 5 段階で表示する。

| 状態 | 意味 |
|---|---|
| 停止中 | 管理対象の `xmcp` プロセスが存在しない |
| 起動中 | プロセスを起動し、初期化完了を待っている |
| 認証待ち | OAuth consent または callback を待っている |
| 接続可能 | MCP endpoint が MCP client から接続可能な状態 |
| エラー | 起動または接続に失敗した状態 |

単純な `process.poll()` だけを成功判定にしない。stdout/stderr の監視、プロセス終了コード、MCP endpoint 到達確認を組み合わせて状態を更新する。

`認証待ち` は `xmcp` の stdout/stderr に出る OAuth consent 関連ログと、MCP endpoint がまだ initialize できない状態から推定する。`xmcp` は初期仕様では改造しないため、状態 API は追加しない。

`接続可能` は HTTP 到達だけで判定しない。HTTP endpoint に到達でき、MCP client library を使った initialize 確認が成功した場合に `接続可能` とする。利用可能な安定した Python MCP client 実装を選定し、選定できない場合だけ最小 HTTP probe を fallback として検討する。

MCP initialize の軽量確認に失敗しても、`xmcp` プロセスが生存している間は `起動中` または `認証待ち` を維持する。startup timeout を超えても接続可能にならない場合に `エラー` へ遷移する。

startup timeout の初期値は 300 秒とし、`xmcp` の `X_OAUTH_CALLBACK_TIMEOUT` デフォルトと揃える。timeout 後はログに基づく推定原因と次の確認項目を GUI に表示する。候補には OAuth 未完了、X Developer App の callback URL 不一致、ネットワーク到達性、OpenAPI spec 取得失敗、ポート競合を含める。

### 11-1. ログ表示

XMCP Manager は `xmcp` の stdout/stderr を読み取り、セッション中に最新 1000 行を内部保持する。GUI には最新 100 行だけを表示する。

ユーザーはログ詳細をコピーできる。初期仕様では永続ログファイルは作成しない。

GUI 表示およびコピー前に、secret-like な値をマスクする。XMCP Manager は `X_OAUTH_PRINT_TOKENS` と `X_OAUTH_PRINT_AUTH_HEADER` を有効化しない。

マスク対象:

- `X_BEARER_TOKEN`、`X_OAUTH_CONSUMER_SECRET`、OAuth token など明示的な secret key の値
- `Authorization` header の値
- 長い token らしいランダム文字列

マスク後の値は全体を `[REDACTED]` に置換する。

## 12. MCP Client 設定更新

XMCP Manager は Claude Desktop と Codex Desktop を MCP client として扱う。どちらも同じ `xmcp` endpoint URL を参照する。

設定更新はユーザーが選択した client だけに適用する。複数 client を選択した場合は、それぞれの設定ファイル内で `xmcp` server エントリだけを管理対象として上書きし、他の MCP server 設定や client 固有設定は保持する。

MCP server key は Claude Desktop では `mcpServers.xmcp`、Codex Desktop では `mcp_servers.xmcp` に固定する。

既存の `xmcp` 設定があり、URL が現在の XMCP Manager endpoint URL と異なる場合は、上書き前に確認を表示する。確認済み状態は app settings の `clientOverwriteAcceptedUrls` に client ごとの「最後に確認した既存 URL」として保存する。既存 URL が保存済み URL と異なる場合は再確認する。

UI では Claude Desktop と Codex Desktop をチェックボックスで表示する。初回はどちらも未選択とし、ユーザーが明示的に選んだ対象だけを更新する。選択状態はアプリ全体設定に保存し、次回以降の初期値として復元する。

MCP client 設定は `Update MCP client config` ボタンなどの明示操作でのみ更新する。「このアカウントで起動」時や port 変更時に自動更新しない。

サーバーが停止中でも MCP client 設定更新は許可する。設定更新は endpoint URL を設定ファイルへ書く操作であり、`xmcp` プロセス状態とは独立して扱う。

対象 client が未選択の場合、更新を止め、Claude Desktop または Codex Desktop を選択するよう表示する。

サーバー起動時、`selectedMcpClients` に入っている client の設定 URL が現在の app settings から生成される URL と不一致の場合は警告を表示する。ただし起動は続行する。未選択 client の設定ファイルは確認しない。

設定ファイルを更新する前に、timestamp 付きバックアップを作成する。バックアップは XMCP Manager の OS 標準ユーザーデータディレクトリ内に保存し、元の client 設定ディレクトリには作成しない。

バックアップは client ごとに最新 10 件を保持し、更新後に古いものを削除する。初期仕様ではバックアップ復元 UI は提供しない。エラー時または設定画面でバックアップ保存場所と手動復元手順を表示する。

既存設定ファイルが存在する場合、読み取りとパースに成功したときだけ更新する。パースに失敗した場合は更新を止め、既存ファイルを変更しない。設定ファイルが存在しない場合は、明示選択された client について必要な親ディレクトリを作成し、新規設定ファイルを作成する。

MCP client 設定の手動 fallback として、Claude Desktop / Codex Desktop の設定スニペットと手動手順を Clients タブで常時表示・コピー可能にする。

自動更新が権限、Store/MSIX 制約、パース失敗、書き込み失敗などで実行できない場合、その場で対象 client の設定スニペットと手動手順を表示し、コピー可能にする。Windows Store build で外部 config 自動更新が不可能な場合は、自動更新を無効化し、この手動 fallback を使用する。

Store validation の結果、`storeValidation.externalConfigWritable[client_id]` が `false` の client では、自動更新操作を disabled にし、手動設定スニペットのコピーを primary action として表示する。

Store validation の結果、`storeValidation.loopbackAvailable` が `false` の場合、Windows Store build では Server 起動を disabled にし、Store build unsupported 状態として表示する。MCP endpoint と OAuth callback は loopback を前提とするため、この状態では中核機能が成立しない。

Store validation の結果、`storeValidation.credentialStoreAvailable` が `false` の場合、Windows Store build では API Credentials 保存を disabled にし、Store build unsupported 状態として表示する。API Credentials は OS キーチェーン / credential store にのみ保存し、JSON fallback は行わない。

Store validation の結果、`storeValidation.userDataWritable` が `false` の場合、Windows Store build では Store build unsupported 状態として表示する。App Settings、Account Metadata、Tool Catalog、backups を保存できないため、アプリ状態を維持できない。

### 12-1. Endpoint URL

URL はアプリ全体設定の `MCP_HOST` と `MCP_PORT` から生成する。

```text
http://127.0.0.1:8000/mcp
```

### 12-2. Claude Desktop 設定

```json
{
  "mcpServers": {
    "xmcp": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Claude Desktop では `mcpServers.xmcp` を XMCP Manager 管理対象として上書きする。

既存 JSON を読み込み、`mcpServers.xmcp` だけを更新し、`indent=2` で整形して書き込む。

| OS | パス |
|---|---|
| Windows | `%APPDATA%\\Claude\\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

### 12-3. Codex Desktop 設定

Codex Desktop は Codex CLI / IDE extension と同じ `config.toml` の MCP 設定を使用する。XMCP Manager は `mcp_servers.xmcp` を管理対象として上書きする。

```toml
[mcp_servers.xmcp]
url = "http://127.0.0.1:8000/mcp"
enabled = true
```

既定の設定ファイルは `~/.codex/config.toml` とする。将来、project scoped `.codex/config.toml` への書き込みを扱う場合は別機能として設計する。

Codex の `config.toml` はコメントや既存 formatting を可能な限り保持して更新する。保持できない場合は更新を止め、既存ファイルを変更しない。

## 13. UI 仕様

GUI は CustomTkinter で実装する。

画面は左ペインの X アカウント一覧と、右ペインのタブビューで構成する。初回起動時またはアカウント未登録時は `Account` タブを表示する。

アカウント一覧の表示名は `displayName (@handle)` とし、`displayName` がない場合は `@handle` を表示する。内部 `uuid` は表示しない。アカウント一覧には credentials 状態の小さな status indicator を表示する。

上部ヘッダーには Server State を常時表示する。詳細なサーバー状態とログは `Server` タブで表示する。

ブロッキング確認は modal dialog として表示する。

右ペインの初期タブ構成:

| タブ | 内容 |
|---|---|
| `Account` | handle、displayName、credentials 状態、credential 編集 |
| `Tools` | Tool Allowlist preset、custom allowlist、Tool Catalog refresh |
| `Clients` | Claude Desktop / Codex Desktop 選択、MCP client 設定更新、手動設定スニペット、URL 不一致警告 |
| `Server` | Start / Stop、Server State 詳細、ログ表示 |
| `Settings` | MCP port、OAuth callback port、Callback URI コピー、backups / recovery links |

画面イメージ:

```text
┌──────────────────────────────────────────────┐
│ XMCP Manager                                 │
│ Server State: 接続可能  Account: @example    │
├──────────────┬───────────────────────────────┤
│ X Accounts   │ Account | Tools | Clients     │
│              │ Server  | Settings            │
│ @account1    │                               │
│ @account2    │ Active tab content            │
│              │                               │
│ [+ Add]      │                               │
└──────────────┴───────────────────────────────┘
```

## 14. プロジェクト構成

```text
/
├── pyproject.toml
├── build.spec
├── scripts/
│   ├── generate_tool_catalog.py
│   └── update_vendored_xmcp.py
├── src/
│   └── xmcp_manager/
│       ├── __init__.py
│       ├── main.py
│       ├── app_settings.py
│       ├── server_manager.py
│       ├── account_store.py
│       ├── client_config.py
│       ├── log_redactor.py
│       ├── migrations.py
│       ├── models.py
│       ├── paths.py
│       ├── tool_allowlist.py
│       ├── resources/
│       │   ├── tool_catalog.json
│       │   └── tool_catalog_overrides.json
│       └── xmcp/
│           ├── server.py
│           └── VENDORED_XMCP_REVISION
└── tests/
    └── fixtures/
        └── fake_xmcp_server.py
```

### 14-1. モジュール責務

| ファイル | 責務 |
|---|---|
| `main.py` | GUI 起動、画面構成、ユーザー操作の結線 |
| `app_settings.py` | App Settings の読み書き、Store validation 状態の保存 |
| `server_manager.py` | `xmcp` プロセス管理、Server State 更新 |
| `account_store.py` | Account Metadata と API Credentials の保存・取得 |
| `client_config.py` | Claude Desktop / Codex Desktop 設定の読み書き |
| `log_redactor.py` | GUI 表示・コピー前の secret-like log redaction |
| `migrations.py` | App Settings、Account Metadata、API Credentials の schema migration |
| `models.py` | dataclass / Enum による共有データモデル |
| `paths.py` | OS ごとのユーザーデータディレクトリと設定パス解決 |
| `tool_allowlist.py` | プリセットと `X_API_TOOL_ALLOWLIST` 生成 |

vendored `xmcp` の取得元 revision は `src/xmcp_manager/xmcp/VENDORED_XMCP_REVISION` に記録する。この値は Tool Catalog generation、About 表示、トラブルシュートに使用できる。

Tool Catalog の `xmcpRevision` は `VENDORED_XMCP_REVISION` と一致しなければならない。不一致の場合、Tool Catalog generation check および release workflow を失敗させる。

### 14-2. Module public API

`paths.py`:

- `get_user_data_dir() -> Path`
- `get_app_settings_path() -> Path`
- `get_accounts_path() -> Path`
- `get_user_tool_catalog_path() -> Path`
- `get_backup_dir(client_id: str) -> Path`
- `get_bundled_resource_path(name: str) -> Path`
- `open_folder(path: Path) -> None`

`app_settings.py`:

- `load_app_settings() -> AppSettings`
- `save_app_settings(settings: AppSettings) -> None`
- `mark_store_validation_current(settings: AppSettings) -> AppSettings`

`account_store.py`:

- `load_accounts() -> AccountMetadataDocument`
- `save_accounts(doc: AccountMetadataDocument) -> None`
- `create_account(handle, display_name) -> Account`
- `delete_account(account_id) -> DeleteResult`
- `get_credentials_status(account_id) -> CredentialsStatus`
- `save_credentials(account_id, partial_credentials, mode) -> None`
- `load_credentials_for_start(account_id) -> ApiCredentials`
- `delete_credentials(account_id) -> None`

`tool_allowlist.py`:

- `load_tool_catalog() -> ToolCatalog`
- `refresh_tool_catalog() -> RefreshResult`
- `generate_allowlist(preset, custom_tools, catalog) -> AllowlistResult`
- `validate_custom_tools(custom_tools, catalog) -> ValidationResult`
- `requires_warning(preset, allowlist, catalog) -> WarningSet`

`client_config.py`:

- `get_client_config_status(client_id, endpoint_url) -> ClientConfigStatus`
- `update_selected_clients(client_ids, endpoint_url) -> UpdateResult`
- `update_claude_config(endpoint_url) -> ClientUpdateResult`
- `update_codex_config(endpoint_url) -> ClientUpdateResult`
- `create_backup(client_id, config_path) -> BackupInfo`
- `prune_backups(client_id, keep=10) -> None`

`server_manager.py`:

- `start(account, credentials, allowlist, app_settings) -> StartResult`
- `stop() -> StopResult`
- `detect_unmanaged(endpoint) -> UnmanagedServerStatus`
- `get_state() -> ServerStateSnapshot`
- `subscribe(listener) -> unsubscribe`
- `copy_logs() -> str`

MCP initialize の軽量確認は `server_manager.py` 内部に置く。Server State 判定の一部として扱い、public API としては露出しない。

### 14-3. Package entry point

アプリ表示名は `XMCP Manager` とする。ウィンドウタイトル、macOS app name、Windows MSIX display name、ユーザーデータ名、キーチェーン service name で同じ表示名を使う。

Python package name は `xmcp_manager` とする。

GUI 起動 entry point は `xmcp-manager` とし、`pyproject.toml` では以下のように定義する。

```toml
[project.scripts]
xmcp-manager = "xmcp_manager.main:main"
```

`main.py` の entry 関数名は `main()` とする。

macOS bundle identifier と Windows MSIX Package Identity Name の仮 identity は `com.imakita3gyo.xmcpmanager` とする。Windows MSIX では Partner Center で確定した identity を優先し、manifest の Package Identity / Publisher と一致させる。

### 14-4. Models and validation

`models.py` には mutable dataclass と Enum を定義する。GUI フォーム編集との相性を優先し、保存時や起動時の validation で整合性を守る。

主要 Enum:

| Enum | 値 |
|---|---|
| `CredentialStatus` | `OK`, `MISSING`, `INVALID`, `INACCESSIBLE` |
| `ToolPreset` | `READ_ONLY`, `BROAD_WRITE`, `FULL_ACCESS`, `CUSTOM` |
| `RiskLevel` | `READ`, `WRITE`, `DESTRUCTIVE`, `SENSITIVE`, `UNKNOWN` |
| `ServerState` | `STOPPED`, `STARTING`, `WAITING_AUTH`, `CONNECTABLE`, `ERROR` |
| `McpClientId` | `CLAUDE_DESKTOP`, `CODEX_DESKTOP` |

JSON serialized value は lower snake string とする。例: `ToolPreset.READ_ONLY` は JSON では `read_only` として保存する。

JSON load 時、未知フィールドは可能な範囲で保持する。各 dataclass は `extra: dict[str, Any]` を持ち、保存時に既知フィールドと merge する。

validation は load 時は緩めに行い、save / start / update など外部状態を変更する直前に厳密に行う。壊れかけたデータでも recovery 表示や部分編集に進める余地を残しつつ、実行前には不正状態を止める。

## 15. 依存パッケージ

依存関係、project version、開発ツール設定は `pyproject.toml` で管理する。開発環境は標準 `venv` + `pip` を使う。

アプリの直接依存は下限指定を基本とする。release build では constraints / lock を生成し、配布ビルドの再現性を確保する。

```text
customtkinter>=5.2.0
keyring>=24.0.0
platformdirs>=4.0.0
tomlkit>=0.12.0
fastmcp
httpx
python-dotenv
requests>=2.31.0
oauthlib>=3.2.2
requests-oauthlib
xai-sdk
xdk
```

vendored `xmcp` の依存関係も `pyproject.toml` に統合する。`xmcp/requirements.txt` は同梱しない。

`cryptography` は直接使用する場合だけ追加する。API Credentials の秘密保存は OS キーチェーンを第一選択とする。

開発依存:

```text
pytest
ruff
mypy
pyinstaller
```

Codex `config.toml` の round-trip 編集には `tomlkit` を使う。Tool Catalog refresh と MCP initialize probe には `httpx` を使う。テストは `pytest`、lint / format は `ruff`、型チェックは `mypy` を使う。

## 16. 配布仕様

初期正式サポート OS は Windows と macOS とする。

| OS | 配布形態 |
|---|---|
| Windows | Microsoft Store 向け MSIX |
| macOS | `.dmg` |

配布目標は「OS 標準の単体アプリ体験」であり、macOS で真の単一バイナリにすることは要求しない。

ビルドは PyInstaller に統一する。開発ビルドは unsigned を許容する。本番配布ビルドでは、macOS は署名済み `.app` を notarization して DMG として配布し、Windows は PyInstaller で生成した exe と同梱ファイルを MSIX package として配布する。

macOS 本番配布では Apple Developer Program の Developer ID 証明書で署名し、hardened runtime を有効化し、notarization 成功後に staple する。

Windows 本番配布では Microsoft Store を使用する。GitHub Actions の Windows runner で PyInstaller により exe を作成し、Windows SDK の `MakeAppx.exe` で MSIX package へ変換する。MSIX manifest、assets、Package Identity、Publisher 情報は Microsoft Store / Partner Center 側の登録情報と一致させる。

Microsoft Store 提出用 MSIX は Store submission flow に従う。Store 外配布用の MSIX を作る場合は、Windows の要件に従い有効な code signing certificate で署名する。Store 外配布用の署名証明書、Apple notarization 認証情報、Windows packaging / Store submission 認証情報は repository に保存しない。GitHub Actions secrets または environment variables から注入する。

MSIX capabilities は最小構成から始め、Microsoft Store validation で必要になった capability だけを追加する。過剰な capability 宣言は避ける。

Windows Store build かどうかは build-time flag `XMCP_STORE_BUILD` で識別する。Store build での自動設定更新可否は、`XMCP_STORE_BUILD` と runtime validation result を組み合わせて判定する。

runtime validation result は app settings の `storeValidation` に保存する。`null` は未検証を表す。`storeValidation.appVersion` が現在の app version と異なる場合は再検証する。

Store build の初回起動時、または `storeValidation.appVersion` が現在の app version と異なる場合、XMCP Manager は Store validation の実行を促す。検証はユーザーの明示操作で実行し、Settings タブから手動実行も可能にする。

`release` ブランチへ push されたとき、GitHub Actions で本番相当の release candidate build を自動作成する。workflow は macOS artifact と Windows MSIX artifact を生成し、macOS は署名・notarization を通した成果物、Windows は MakeAppx で作成した MSIX を release candidate artifact として扱う。

`release` ブランチ push では署名済み release candidate artifact を作成する。release candidate artifact の retention は 14 日とする。

`v*` tag push では、tag と `pyproject.toml` の project version が一致することを検証する。例: `v1.2.3` tag では `pyproject.toml` version は `1.2.3` でなければならない。不一致の場合、release workflow を失敗させる。

`v*` tag push では GitHub draft release を作成し、署名済み macOS DMG を添付する。即時 published release にはしない。

Windows MSIX は Store package validation 合格までは release candidate artifact としてのみ扱い、GitHub draft release には添付しない。Store package validation 合格後に、Windows MSIX を draft release 添付対象にできる。

release workflow には最低限以下の検証を含める。

- lint
- unit tests
- Tool Catalog generation check
- PyInstaller build
- macOS signing / notarization
- Windows MakeAppx MSIX packaging
- artifact smoke check

Windows Store / MSIX 特有の検証は通常の artifact smoke check と分け、Store package validation として定義する。初期は手動検証を必須とし、CI では可能な範囲だけ自動化する。

Store package validation の必須項目:

- MSIX install / launch
- `%APPDATA%\Claude\claude_desktop_config.json` 更新
- `~/.codex/config.toml` 更新
- `127.0.0.1:<mcpPort>/mcp` で xmcp server 起動
- `127.0.0.1:<oauthCallbackPort>/oauth/callback` callback listener 起動
- Windows Credential Manager への保存・読み出し・削除
- Tool Catalog / app settings / accounts の user data 書き込み
- Microsoft Store validation / certification kit 相当のチェック

## 17. 動作確認

### 17-1. 開発時確認

1. 仮想環境を作成する
2. 依存パッケージをインストールする
3. `python -m xmcp_manager.main` または `xmcp-manager` で GUI を起動する
4. X アカウントを追加する
5. API Credentials を保存する
6. Tool Allowlist プリセットを選ぶ
7. MCP client 設定を更新する
8. `xmcp` を起動する
9. OAuth consent が必要な場合はブラウザで認証する
10. Server State が `接続可能` になることを確認する
11. 選択した MCP client から X アカウント情報を取得できることを確認する

### 17-2. 主要検証観点

- Account Metadata に秘密情報が保存されない
- API Credentials が OS キーチェーンに保存される
- Claude Desktop では `mcpServers.xmcp` だけが更新され、他の設定が保持される
- Codex Desktop では `mcp_servers.xmcp` だけが更新され、他の設定が保持される
- ポート変更時に `xmcp` env と MCP client URL が一致する
- Tool Allowlist が `X_API_TOOL_ALLOWLIST` に反映される
- アカウント切り替え時に既存 `xmcp` が停止し、新しい env で再起動する
- OAuth 認証待ちが GUI 上で識別できる
- OpenAPI spec 取得失敗が GUI 上で識別できる

### 17-3. テスト方針

unit test は以下を対象にする。

- Account Metadata schema load / save / migration
- API Credentials validation と keyring adapter mock
- Tool Catalog load / fallback / refresh parse
- Tool Allowlist preset generation
- log redaction
- MCP client config writer for Claude JSON
- MCP client config writer for Codex TOML
- Server State transition logic with fake process / logs

CustomTkinter UI の自動テストは初期仕様に含めない。UI は手動 smoke checklist で確認し、ロジックは unit test で検証する。

release workflow の artifact smoke check は以下を確認する。

- アプリが起動する
- App Settings がユーザーデータディレクトリに作成できる
- 同梱 `resources/tool_catalog.json` を読み込める
- `xmcp/server.py` が同梱されている
- secret 値なしで credentials missing を表示できる
- GUI を閉じられる

X API 実接続テストは通常の CI / release workflow に含めない。従量課金、OAuth consent、外部依存があるため、必要時の手動検証として扱う。

手動 smoke checklist は以下を含める。

- 新規アカウント追加
- credentials 保存 / 再入力 / missing 表示
- Tool preset 切り替え
- custom allowlist invalid tool で起動停止
- broad write warning
- full access warning
- unknown tool warning
- MCP client config backup 作成
- Claude config 更新
- Codex config 更新
- managed process start / stop
- unmanaged process conflict 表示
- log redaction
- recovery 案内表示

Server State と MCP initialize 周辺のテスト用に `tests/fixtures/fake_xmcp_server.py` を用意する。fake xmcp server は以下を再現できるようにする。

- immediate connectable
- delayed connectable
- oauth waiting log then connectable
- startup failure
- port already in use
- emits secret-like logs for redaction test

## 18. 参考情報

| リソース | URL |
|---|---|
| xmcp GitHub | https://github.com/xdevplatform/xmcp |
| X Developer Portal | https://developer.x.com |
| FastMCP ドキュメント | https://gofastmcp.com |
| Claude Desktop MCP設定 | https://docs.claude.ai/docs/mcp |
| CustomTkinter | https://github.com/TomSchimansky/CustomTkinter |
| PyInstaller ドキュメント | https://pyinstaller.org/en/stable/ |
| MakeAppx / MSIX packaging | https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool |
| MSIX signing | https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview |

---

本仕様は初回策定時に 2026-06-24 時点の `xdevplatform/xmcp` master ブランチ README / `server.py` / `env.example` を確認して作成している。実装時に同梱する `xmcp` の正は `src/xmcp_manager/xmcp/VENDORED_XMCP_REVISION` に記録された revision とする。
