# DataSensei Frontend

React + Vite + Tailwind CSS frontend for the Text-to-SQL chatbot.

## Features

- Chat interface for natural language queries
- File upload (CSV and PDF support)
- Session management
- Real-time query results display
- System health monitoring

## Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:3000`

## API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000`

### Endpoints Used

- `GET /get_system_health` - Check system status
- `POST /upload` - Upload CSV or PDF files
- `POST /query` - Execute natural language queries

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── UploadForm.jsx
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── package.json
```

## Development

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```
