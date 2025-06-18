# 🤖 AI MoM Assistant

Transform meeting recordings into professional Minutes of Meeting with AI-powered transcription and summarization.

## ✨ Features

- 🎤 Audio upload and transcription
- ⏱️ Timestamp-based segment selection
- 🎭 Multiple tone and audience options
- 📝 Context-aware MoM generation
- 🔄 Iterative refinement
- 📥 Multiple export formats

## 🚀 Quick Start

### Local Development

1. **Clone & Setup**
   ```bash
   git clone <your-repo>
   cd ai-mom-assistant
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

3. **Run Application**
   ```bash
   streamlit run app.py
   ```

### 🌐 Deploy to Streamlit Cloud

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial AI MoM Assistant"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Visit https://share.streamlit.io
   - Connect your GitHub repository
   - Add secrets in settings:
     - `OPENAI_API_KEY = "your_key_here"`

3. **Access Your App**
   - Your app will be available at: `https://your-app-name.streamlit.app`

## 🔧 Configuration

### API Keys Required
- **OpenAI API Key**: For Whisper transcription and GPT text generation
- Sign up at: https://platform.openai.com/

### Supported Audio Formats
- MP3, WAV, M4A, OGG
- Max file size: 25MB
- Duration: Up to 25 minutes per file

## 💡 Usage Tips

1. **Best Audio Quality**: Use clear, noise-free recordings
2. **Context Matters**: Provide detailed meeting context for better results
3. **Iterative Refinement**: Use the refinement options to perfect your MoM
4. **Previous Meeting Context**: Link previous meetings for continuity

## 🛠️ Technical Architecture

- **Frontend**: Streamlit (Python web framework)
- **Transcription**: OpenAI Whisper API
- **Text Generation**: OpenAI GPT-3.5/4
- **Deployment**: Streamlit Cloud (free tier)
- **Storage**: Session-based (no persistent storage)

## 📊 Demo Mode

The app includes demo mode with sample meeting transcript for testing without API keys.

## 🔒 Privacy & Security

- No audio files stored permanently
- Transcripts processed in memory only
- API keys stored securely in Streamlit secrets
- No user data persistence

## 🚧 Roadmap (V2 Features)

- [ ] Real-time voice recording
- [ ] PDF export with formatting
- [ ] Calendar integration
- [ ] Team collaboration features
- [ ] Analytics dashboard
- [ ] Multi-language support

## 📞 Support

For technical issues or feature requests, please create an issue in the repository.
```

### 🐳 Optional: Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 🚀 Deployment Instructions

#### Option 1: Streamlit Cloud (Recommended - Free)

1. **Prepare Repository**
   ```bash
   # Create new repository
   mkdir ai-mom-assistant
   cd ai-mom-assistant
   
   # Copy the main app code (app.py) and requirements.txt
   # Add all configuration files
   
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Go to https://share.streamlit.io
   - Click "New app"
   - Connect your GitHub repository
   - Set main file path: `app.py`
   - Add secrets in Advanced Settings:
     ```
     OPENAI_API_KEY = "sk-your-actual-api-key-here"
     ```
   - Click "Deploy"

3. **Access Your Live App**
   - URL: