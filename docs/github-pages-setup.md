# GitHub Pages + カスタムドメイン設定

## アーキテクチャ選択

### 推奨構成: フロントエンド/バックエンド分離

```
your-domain.com
├── spotpdf.your-domain.com    # GitHub Pages (静的サイト)
└── api.your-domain.com        # 別サーバー (Flask API)
```

## セットアップ手順

### 1. Publicリポジトリ作成
```bash
# フロントエンド専用のPublicリポジトリ
gh repo create spotpdf-web-frontend --public
```

### 2. 静的フロントエンド構成
```
spotpdf-web-frontend/
├── index.html          # メインページ
├── login.html         # ログインページ
├── assets/
│   ├── css/
│   ├── js/
│   └── images/
├── _config.yml        # Jekyll設定
└── CNAME             # カスタムドメイン設定
```

### 3. CNAME設定
```
# CNAME ファイルの内容
spotpdf.your-domain.com
```

### 4. DNS設定 (your domain provider)
```
# A records for GitHub Pages
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153

# または CNAME record
spotpdf.your-domain.com -> your-username.github.io
```

## JavaScript Frontend (GitHub Pages)

### API通信設定
```javascript
// config.js
const API_BASE_URL = 'https://api.your-domain.com';
const GOOGLE_CLIENT_ID = 'your-public-client-id';

// api.js  
async function uploadPDFs(oldPdf, newPdf, settings) {
    const formData = new FormData();
    formData.append('old_pdf', oldPdf);
    formData.append('new_pdf', newPdf);
    formData.append('settings', JSON.stringify(settings));
    
    const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
        credentials: 'include' // セッション管理
    });
    
    return response.json();
}
```

## バックエンドAPI (別サーバー)

### CORS設定追加
```python
# web_app.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=['https://spotpdf.your-domain.com'], supports_credentials=True)
```

### デプロイオプション

#### A) VPS/クラウドサーバー
- AWS EC2, Google Cloud Compute, Azure VM
- Heroku, Railway, Render.com

#### B) コンテナサービス  
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances

#### C) サーバーレス
- Vercel Functions
- Netlify Functions  
- AWS Lambda (ただしPDF処理には制限あり)
```

## GitHub Actions設定

### 静的サイトデプロイ
```yaml
# .github/workflows/deploy-pages.yml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
    
    - name: Build frontend
      run: |
        npm install
        npm run build
    
    - name: Deploy to GitHub Pages
      uses: peaceiris/actions-gh-pages@v3
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
        publish_dir: ./dist
        cname: spotpdf.your-domain.com
```

## セキュリティ考慮事項

### 1. API認証
```javascript
// JWT token management
localStorage.setItem('auth_token', token);

fetch(`${API_BASE_URL}/upload`, {
    headers: {
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
    }
});
```

### 2. HTTPS強制
```yaml
# _config.yml
enforce_ssl: spotpdf.your-domain.com
```

### 3. Content Security Policy
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               connect-src 'self' https://api.your-domain.com https://accounts.google.com;
               script-src 'self' https://accounts.google.com;">
```