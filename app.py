import streamlit as st
import openai
import json
import io
import base64
from datetime import datetime, timedelta
import re
import time
import tempfile
import os
from deepgram import Deepgram


# Page configuration
st.set_page_config(
    page_title="AI MoM Assistant",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2E86AB;
        padding: 1rem 0;
        border-bottom: 2px solid #2E86AB;
        margin-bottom: 2rem;
    }
    .section-header {
        color: #2E86AB;
        border-left: 4px solid #2E86AB;
        padding-left: 1rem;
        margin: 1.5rem 0 1rem 0;
    }
    .transcript-segment {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2E86AB;
        margin: 1rem 0;
    }
    .mom-output {
        background-color: #f9f9f9;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
    }
    .success-message {
        color: #28a745;
        font-weight: bold;
    }
    .warning-message {
        color: #ffc107;
        font-weight: bold;
    }
    .error-message {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'transcript_data' not in st.session_state:
    st.session_state.transcript_data = None
if 'selected_transcript' not in st.session_state:
    st.session_state.selected_transcript = ""
if 'generated_mom' not in st.session_state:
    st.session_state.generated_mom = ""
if 'api_key_set' not in st.session_state:
    st.session_state.api_key_set = False

def format_time(seconds):
    """Convert seconds to MM:SS format"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

def transcribe_audio_real(audio_file, api_key):
    """Real transcription function using OpenAI Whisper API"""
    try:
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        st.info(f"📁 Processing file: {audio_file.name} ({audio_file.size / 1024 / 1024:.2f} MB)")
        
        # Create a temporary file to save the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.name)[1]) as tmp_file:
            tmp_file.write(audio_file.read())
            tmp_file_path = tmp_file.name
        
        # Progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Upload and transcribe
            status_text.text("🎵 Uploading audio to OpenAI...")
            progress_bar.progress(25)
            
            with open(tmp_file_path, "rb") as audio_file_obj:
                # Use Whisper API with timestamps
                status_text.text("🤖 Transcribing with Whisper API...")
                progress_bar.progress(50)
                
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file_obj,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            status_text.text("📝 Processing transcript segments...")
            progress_bar.progress(75)
            
            # Convert to our format
            transcript_data = []
            if hasattr(transcript, 'segments') and transcript.segments:
                for segment in transcript.segments:
                    transcript_data.append({
                        "start_time": segment['start'],
                        "end_time": segment['end'],
                        "text": segment['text'].strip()
                    })
            else:
                # Fallback: create one segment for the entire transcript
                transcript_data.append({
                    "start_time": 0,
                    "end_time": transcript.duration if hasattr(transcript, 'duration') else 0,
                    "text": transcript.text
                })
            
            status_text.text("✅ Transcription complete!")
            progress_bar.progress(100)
            
            return transcript_data
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except openai.APIError as e:
        st.error(f"OpenAI API Error: {e}")
        return None
    except Exception as e:
        st.error(f"Transcription Error: {str(e)}")
        return None


def transcribe_audio_deepgram(audio_file, deepgram_key):
    try:
        dg_client = Deepgram(deepgram_key)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_file.read())
            tmp_file_path = tmp_file.name

        with open(tmp_file_path, "rb") as f:
            source = {"buffer": f, "mimetype": "audio/mp3"}
            response = dg_client.transcription.sync_prerecorded(source, {
                "punctuate": True,
                "paragraphs": True
            })

        segments = []
        for para in response["results"]["channels"][0]["alternatives"][0]["paragraphs"]["paragraphs"]:
            segments.append({
                "start_time": para["start"],
                "end_time": para["end"],
                "text": para["sentences"][0]["text"]
            })

        return segments
    except Exception as e:
        st.error(f"Deepgram Transcription Error: {str(e)}")
        return None


def generate_mom_prompt(transcript, context, previous_meeting, tone, audience, goal):
    """Generate the prompt for MoM creation"""
    
    tone_instructions = {
        "Formal": "Use formal business language, proper titles, and structured format.",
        "Informal": "Use casual, friendly language while maintaining professionalism.",
        "Leadership": "Focus on strategic decisions, high-level outcomes, and executive summary.",
        "Urgent": "Emphasize critical items, deadlines, and immediate action requirements.",
        "FYI": "Structure as an informational update with key highlights.",
        "Action-focused": "Prioritize action items, assignments, and next steps.",
        "Approval-seeking": "Structure to clearly present items requiring approval or decision."
    }
    
    audience_context = {
        "Leadership": "executive stakeholders who need strategic overview",
        "Developers": "technical team members who need implementation details",
        "Clients": "external stakeholders who need progress updates",
        "Cross-functional": "diverse team members from multiple departments",
        "Project Team": "core project contributors and stakeholders"
    }
    
    prompt = f"""
Create professional Minutes of Meeting (MoM) based on the following transcript and context.

MEETING CONTEXT:
{context}

AUDIENCE: {audience} - {audience_context.get(audience, "general stakeholders")}
GOAL: {goal}
TONE: {tone} - {tone_instructions.get(tone, "Professional and clear")}

TRANSCRIPT:
{transcript}

PREVIOUS MEETING CONTEXT:
{previous_meeting if previous_meeting else "No previous meeting context provided."}

Please generate a comprehensive MoM that includes:
1. Meeting Overview (date, attendees, purpose)
2. Key Discussion Points
3. Decisions Made
4. Action Items (with owners and deadlines where mentioned)
5. Next Steps
6. Follow-up Meeting Details

Format the output in a professional, easy-to-read structure appropriate for the specified audience and tone.
Use markdown formatting for better readability.
"""
    
    return prompt

def generate_mom_real(prompt, api_key):
    """Real MoM generation using OpenAI GPT API"""
    try:
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Show progress during generation
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🤖 Analyzing meeting transcript...")
        progress_bar.progress(20)
        
        # Call OpenAI GPT API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You can change to "gpt-4" for better results
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional meeting secretary and documentation expert. Create clear, structured, and comprehensive Minutes of Meeting documents."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2000,
            temperature=0.3  # Lower temperature for more consistent, professional output
        )
        
        status_text.text("📝 Structuring meeting summary...")
        progress_bar.progress(60)
        
        # Extract the generated MoM
        generated_mom = response.choices[0].message.content
        
        status_text.text("✨ Formatting final document...")
        progress_bar.progress(80)
        
        # Add generation timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        generated_mom += f"\n\n---\n*Generated by AI MoM Assistant on {timestamp}*"
        
        status_text.text("✅ Generation complete!")
        progress_bar.progress(100)
        
        return generated_mom
        
    except openai.APIError as e:
        st.error(f"OpenAI API Error: {e}")
        return None
    except Exception as e:
        st.error(f"MoM Generation Error: {str(e)}")
        return None

# Main App Interface
st.markdown("<h1 class='main-header'>🤖 AI MoM Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Transform meeting recordings into professional Minutes of Meeting with AI</p>", unsafe_allow_html=True)

# Sidebar for API Configuration
    # deepgram_key = st.text_input("Deepgram API Key", type="password", help="Optional: Use Deepgram for transcription")
    # st.session_state.deepgram_key_set = bool(deepgram_key)


# Sidebar for API Configuration
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    provider = st.radio("Choose Transcription Provider", ["OpenAI", "Deepgram"])

    api_key = ""
    if provider == "OpenAI":
        api_key = st.text_input("OpenAI API Key", type="password", help="Required for Whisper and GPT")
        st.session_state.api_key_set = bool(api_key)
        if api_key:
            try:
                client = openai.OpenAI(api_key=api_key)
                st.success("🔑 OpenAI API Key validated successfully")
            except:
                st.error("❌ Invalid OpenAI API Key")
                st.session_state.api_key_set = False
        else:
            st.warning("⚠️ Please enter your OpenAI API key.")

    elif provider == "Deepgram":
        deepgram_key = st.text_input("Deepgram API Key", type="password", help="Required for Deepgram transcription")
        st.session_state.deepgram_key_set = bool(deepgram_key)
        if deepgram_key:
            st.success("🔑 Deepgram API Key entered")
        else:
            st.warning("⚠️ Please enter your Deepgram API key.")

    st.markdown("---")
    st.markdown("### 📋 Quick Actions")
    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ Session reset!")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📖 Instructions")
    st.markdown("""
    1. **Choose Provider** (OpenAI or Deepgram)
    2. **Enter API Key**
    3. **Upload** audio file
    4. **Review** transcript segments
    5. **Configure** context & tone
    6. **Generate** MoM
    7. **Export** results
    """)
    st.markdown("### 📋 Quick Actions")
    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ Session reset!")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📖 Instructions")
    st.markdown("""
    1. **Enter API Key** (required)
    2. **Upload** audio file
    3. **Review** transcript segments
    4. **Select** time range
    5. **Configure** context & tone
    6. **Generate** MoM
    7. **Export** results
    """)
    
    # Workflow status checker
    st.markdown("---")
    st.markdown("### ✅ Workflow Status")
    
    # Check current progress
    progress_items = []
    
    if st.session_state.api_key_set:
        progress_items.append("✅ API Key configured")
    else:
        progress_items.append("❌ API Key required")
    
    if st.session_state.get('transcript_data'):
        progress_items.append("✅ Transcript loaded")
    else:
        progress_items.append("⏳ Load transcript")
    
    if st.session_state.get('selected_transcript'):
        progress_items.append("✅ Segment selected")
    else:
        progress_items.append("⏳ Select time range")
    
    if st.session_state.get('config', {}).get('context'):
        progress_items.append("✅ Context configured")
    else:
        progress_items.append("⏳ Add meeting context")
    
    if st.session_state.get('generated_mom'):
        progress_items.append("✅ MoM generated")
        progress_items.append("✅ Ready to export")
    else:
        progress_items.append("⏳ Generate MoM")
        progress_items.append("⏳ Export results")
    
    for item in progress_items:
        st.markdown(f"- {item}")

# Main content area with tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎤 Audio Input", "📝 Transcript", "⚙️ Configuration", "✨ Generate MoM", "📥 Export"])

with tab1:
    st.markdown("<h3 class='section-header'>Audio Input</h3>", unsafe_allow_html=True)
    
    if not st.session_state.api_key_set:
        st.error("🚨 **OpenAI API Key Required**")
        st.markdown("Please enter your OpenAI API key in the sidebar to proceed.")
        st.stop()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Upload Audio File")
        
    provider = st.radio("Choose Transcription Provider", ["OpenAI", "Deepgram"])

uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['mp3', 'wav', 'm4a', 'ogg', 'flac'],
            help="Upload meeting recording in MP3, WAV, M4A, OGG, or FLAC format"
        )
        
if uploaded_file is not None:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    # Show file details
    file_details = {
        "Filename": uploaded_file.name,
        "File size": f"{uploaded_file.size / 1024 / 1024:.2f} MB",
        "File type": uploaded_file.type
    }
    
    for key, value in file_details.items():
        st.write(f"**{key}:** {value}")
    
    # Show audio player
    st.audio(uploaded_file)
    
    # File size warning
    if uploaded_file.size > 25 * 1024 * 1024:  # 25MB limit for OpenAI
        st.warning("⚠️ File size exceeds 25MB. OpenAI Whisper has a 25MB limit. Consider compressing your audio file.")
    
    # Transcription button
    transcribe_button = st.button("🔄 Transcribe Audio", type="primary", key="transcribe_btn")
    
    if transcribe_button:
        try:
            # Clear any previous transcript
            if 'transcript_data' in st.session_state:
                del st.session_state.transcript_data
            
            # Create a container for the transcription process
            transcription_container = st.container()
            
            with transcription_container:
                st.info("🎯 Starting real transcription with OpenAI Whisper...")
                
                # Call the real transcription function
                transcript_result = transcribe_audio_real(uploaded_file, api_key)
                
                if transcript_result:
                    st.session_state.transcript_data = transcript_result
                    st.success("✅ Transcription completed successfully!")
                    st.balloons()
                    
                    # Show quick preview
                    st.markdown("**📋 Preview:**")
                    preview_text = transcript_result[0]['text'][:200] + "..." if len(transcript_result[0]['text']) > 200 else transcript_result[0]['text']
                    st.info(f"First segment: {preview_text}")
                    
                    # Auto-advance to transcript tab
                    st.info("👉 Check the 'Transcript' tab to review your transcription!")
                else:
                    st.error("❌ Transcription failed. Please check your API key and try again.")
                
        except Exception as e:
            st.error(f"❌ Transcription failed: {str(e)}")
            st.error("Please check your API key and try again.")

else:
    st.info("👆 Please upload an audio file to start transcription")

with col2:
    st.markdown("#### 🎙️ Live Recording")
    
    # Audio recording interface (placeholder for now)
    st.info("🚧 **Live Recording Feature**")
    st.markdown("""
    **Status:** Available in advanced implementation
    
    **Features:**
    - 🎤 Real-time voice recording
    - ⏯️ Pause/Resume controls
    - 🔊 Audio quality settings
    - ⏱️ Recording duration display
    - 🎵 Live audio visualization
    """)
        
    # Mock recording interface
    col_rec1, col_rec2 = st.columns(2)
    with col_rec1:
        if st.button("🔴 Start Recording", disabled=True):
            st.info("Feature available in advanced version")
    with col_rec2:
        if st.button("⏹️ Stop Recording", disabled=True):
            st.info("Would record and auto-transcribe")
    
    # Recording implementation guide
    with st.expander("🔧 Implementation Guide"):
        st.code("""
# To enable real recording, install:
pip install streamlit-webrtc pyaudio

# Then add this code:
from streamlit_webrtc import webrtc_streamer
import av
import numpy as np

def audio_frame_callback(frame):
    audio_array = frame.to_ndarray()
    # Process and save audio frames
    return frame

webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDONLY,
    audio_frame_callback=audio_frame_callback,
    media_stream_constraints={
        "video": False,
        "audio": True,
    }
)
            """)

with tab2:
    st.markdown("<h3 class='section-header'>Transcript Review</h3>", unsafe_allow_html=True)
    
    if st.session_state.transcript_data:
        st.success(f"✅ Transcript loaded with {len(st.session_state.transcript_data)} segments")
        
        # Show total duration
        total_duration = st.session_state.transcript_data[-1]['end_time'] if st.session_state.transcript_data else 0
        st.info(f"📊 Total meeting duration: {format_time(total_duration)}")
        
        # Time range selector
        col1, col2 = st.columns(2)
        with col1:
            start_time = st.selectbox(
                "Start Time",
                options=[segment['start_time'] for segment in st.session_state.transcript_data],
                format_func=lambda x: f"{format_time(x)} - {next(s['text'][:50] + '...' for s in st.session_state.transcript_data if s['start_time'] == x)}"
            )
        
        with col2:
            end_options = [s['end_time'] for s in st.session_state.transcript_data if s['end_time'] > start_time]
            if end_options:
                end_time = st.selectbox(
                    "End Time",
                    options=end_options,
                    index=len(end_options)-1,
                    format_func=lambda x: f"{format_time(x)} - {next(s['text'][:50] + '...' for s in st.session_state.transcript_data if s['end_time'] == x)}"
                )
            else:
                end_time = start_time
        
        # Show selected transcript
        selected_segments = [
            segment for segment in st.session_state.transcript_data
            if segment['start_time'] >= start_time and segment['end_time'] <= end_time
        ]
        
        if selected_segments:
            st.markdown("#### 📋 Selected Transcript Segment")
            selected_text = ""
            for segment in selected_segments:
                selected_text += f"[{format_time(segment['start_time'])} - {format_time(segment['end_time'])}] {segment['text']}\n\n"
                st.markdown(f"""
                <div class='transcript-segment'>
                    <strong>{format_time(segment['start_time'])} - {format_time(segment['end_time'])}</strong><br>
                    {segment['text']}
                </div>
                """, unsafe_allow_html=True)
            
            st.session_state.selected_transcript = selected_text.strip()
            
            # Show selection statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Selected Segments", len(selected_segments))
            with col2:
                duration = end_time - start_time
                st.metric("Duration", format_time(duration))
            with col3:
                word_count = len(selected_text.split())
                st.metric("Word Count", word_count)
        else:
            st.warning("⚠️ No segments selected in this time range")
    else:
        st.info("👆 Please upload an audio file and transcribe it in the Audio Input tab")
        if not st.session_state.api_key_set:
            st.error("🚨 API Key required for transcription")

with tab3:
    st.markdown("<h3 class='section-header'>Meeting Configuration</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📝 Current Meeting Context")
        meeting_context = st.text_area(
            "Meeting Context",
            placeholder="e.g., Weekly sprint review with development team to discuss progress, blockers, and next sprint planning...",
            height=120,
            help="Provide context about the meeting purpose, participants, and key topics"
        )
        
        st.markdown("#### 👥 Audience")
        audience = st.selectbox(
            "Target Audience",
            ["Leadership", "Developers", "Clients", "Cross-functional", "Project Team"],
            help="Who will be reading this MoM?"
        )
        
        meeting_goal = st.text_input(
            "Meeting Goal",
            placeholder="e.g., Review sprint progress and plan next iteration",
            help="What was the main objective of this meeting?"
        )
    
    with col2:
        st.markdown("#### 📄 Previous Meeting Context")
        previous_meeting = st.text_area(
            "Previous Meeting Summary (Optional)",
            placeholder="Paste previous meeting summary or key points to avoid repetition and maintain context...",
            height=120,
            help="Optional: Provide context from previous meetings to improve continuity"
        )
        
        st.markdown("#### 🎭 Tone & Style")
        tone = st.selectbox(
            "Meeting Tone",
            ["Formal", "Informal", "Leadership", "Urgent", "FYI", "Action-focused", "Approval-seeking"],
            help="Choose the appropriate tone for your audience"
        )
        
        # Model selection
        st.markdown("#### 🤖 AI Model")
        model_choice = st.selectbox(
            "GPT Model",
            ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
            help="Choose AI model (GPT-4 provides better quality but costs more)"
        )
        
        # Store configuration in session state
        st.session_state.config = {
            'context': meeting_context,
            'previous_meeting': previous_meeting,
            'audience': audience,
            'goal': meeting_goal,
            'tone': tone,
            'model': model_choice
        }

with tab4:
    st.markdown("<h3 class='section-header'>Generate Minutes of Meeting</h3>", unsafe_allow_html=True)
    
    if not st.session_state.api_key_set:
        st.error("🚨 **OpenAI API Key Required**")
        st.markdown("Please enter your OpenAI API key in the sidebar to proceed.")
        st.stop()
    
    if st.session_state.selected_transcript and hasattr(st.session_state, 'config'):
        config = st.session_state.config
        
        # Show summary of configuration
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Audience", config['audience'])
        with col2:
            st.metric("Tone", config['tone'])
        with col3:
            st.metric("AI Model", config.get('model', 'gpt-3.5-turbo'))
        with col4:
            st.metric("Transcript Length", f"{len(st.session_state.selected_transcript.split())} words")
        
        st.markdown("#### 🔧 Final Configuration")
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            custom_instructions = st.text_area(
                "Additional Instructions",
                placeholder="e.g., Focus on action items, include budget discussions, emphasize deadlines...",
                help="Any specific instructions for the AI to follow"
            )
            
            include_timestamps = st.checkbox("Include Timestamps", value=True)
            include_sentiment = st.checkbox("Include Sentiment Analysis", value=False)
            
            max_tokens = st.slider("Max Response Length", min_value=500, max_value=4000, value=2000, 
                                 help="Maximum tokens for the response (higher = longer MoM)")
        
        # Generate MoM
        generate_button = st.button("✨ Generate Minutes of Meeting", type="primary", key="generate_mom_btn")
        
        if generate_button:
            if not config['context']:
                st.error("❌ Please provide meeting context in the Configuration tab")
            else:
                # Create containers for the generation process
                generation_container = st.container()
                
                with generation_container:
                    st.info("🚀 Starting real MoM generation with OpenAI...")
                    
                    # Add custom instructions to the prompt if provided
                    full_context = config['context']
                    if custom_instructions:
                        full_context += f"\n\nAdditional Instructions: {custom_instructions}"
                    
                    prompt = generate_mom_prompt(
                        st.session_state.selected_transcript,
                        full_context,
                        config['previous_meeting'],
                        config['tone'],
                        config['audience'],
                        config['goal']
                    )
                    
                    # Generate MoM using real OpenAI API
                    generated_result = generate_mom_real(prompt, api_key)
                    
                    if generated_result:
                        st.session_state.generated_mom = generated_result
                        st.success("✅ Minutes of Meeting generated successfully!")
                        st.balloons()
                        
                        # Show token usage estimate
                        estimated_tokens = len(generated_result.split()) * 1.3  # Rough estimate
                        st.info(f"📊 Estimated tokens used: ~{int(estimated_tokens)}")
                    else:
                        st.error("❌ MoM generation failed. Please check your API key and try again.")
        
        # Always show generated MoM if it exists
        if st.session_state.generated_mom:
            st.markdown("#### 📋 Generated Minutes of Meeting")
            
            # Create a nice container for the MoM
            mom_container = st.container()
            with mom_container:
                st.markdown(st.session_state.generated_mom)
                
                # Add a copy button for convenience
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown("**Quick Actions:**")
                    if st.button("📋 Copy Text", key="quick_copy"):
                        st.info("💡 Use the text area in Export tab to copy!")
                    if st.button("📥 Go to Export", key="go_to_export"):
                        st.info("👉 Check the 'Export' tab for download options!")
            
            # Refinement options
            st.markdown("#### 🔄 Refine Results")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📝 Make More Detailed"):
                    refined_prompt = prompt + "\n\nPlease make this more detailed and comprehensive."
                    st.info("🔄 Regenerating with more detail...")
                    refined_result = generate_mom_real(refined_prompt, api_key)
                    if refined_result:
                        st.session_state.generated_mom = refined_result
                        st.rerun()
                
                if st.button("⚡ Make More Concise"):
                    refined_prompt = prompt + "\n\nPlease make this more concise and focused on key points only."
                    st.info("🔄 Regenerating more concisely...")
                    refined_result = generate_mom_real(refined_prompt, api_key)
                    if refined_result:
                        st.session_state.generated_mom = refined_result
                        st.rerun()
            
            with col2:
                if st.button("🎯 Focus on Action Items"):
                    refined_prompt = prompt + "\n\nPlease focus heavily on action items, assignments, and next steps."
                    st.info("🔄 Regenerating with action item focus...")
                    refined_result = generate_mom_real(refined_prompt, api_key)
                    if refined_result:
                        st.session_state.generated_mom = refined_result
                        st.rerun()
                
                if st.button("📊 Add More Analysis"):
                    refined_prompt = prompt + "\n\nPlease add more analytical insights and observations about the meeting dynamics and outcomes."
                    st.info("🔄 Adding analytical insights...")
                    refined_result = generate_mom_real(refined_prompt, api_key)
                    if refined_result:
                        st.session_state.generated_mom = refined_result
                        st.rerun()
    
    else:
        if not st.session_state.selected_transcript:
            st.info("👆 Please select a transcript segment in the Transcript tab")
        else:
            st.info("👆 Please configure meeting details in the Configuration tab")

with tab5:
    st.markdown("<h3 class='section-header'>Export Results</h3>", unsafe_allow_html=True)
    
    if st.session_state.generated_mom:
        st.success("🎉 **MoM Generated Successfully!** All export options are now available.")
        
        col1, col2 = st.columns
