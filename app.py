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

def real_transcribe_audio(audio_file, api_key):
    """Real transcription function using OpenAI Whisper API"""
    try:
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Show processing status
        st.info(f"📁 Processing file: {audio_file.name} ({audio_file.size} bytes)")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create a temporary file to save the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.name)[1]) as tmp_file:
            tmp_file.write(audio_file.read())
            tmp_file_path = tmp_file.name
        
        try:
            status_text.text("🎵 Uploading to OpenAI Whisper...")
            progress_bar.progress(20)
            
            # Open the temporary file for transcription
            with open(tmp_file_path, "rb") as audio_file_obj:
                # Call OpenAI Whisper API with timestamp support
                status_text.text("🤖 Transcribing with OpenAI Whisper...")
                progress_bar.progress(50)
                
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file_obj,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
                
                progress_bar.progress(80)
                status_text.text("📝 Processing transcript segments...")
                
                # Convert OpenAI response to our format
                transcript_data = []
                if hasattr(transcript, 'segments') and transcript.segments:
                    for segment in transcript.segments:
                        transcript_data.append({
                            "start_time": segment.start,
                            "end_time": segment.end,
                            "text": segment.text.strip()
                        })
                else:
                    # Fallback: create single segment if no segments returned
                    transcript_data.append({
                        "start_time": 0,
                        "end_time": 60,  # Placeholder duration
                        "text": transcript.text
                    })
                
                progress_bar.progress(100)
                status_text.text("✅ Transcription complete!")
                
                return transcript_data
                
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except openai.AuthenticationError:
        st.error("❌ Invalid OpenAI API key. Please check your API key.")
        return None
    except openai.RateLimitError:
        st.error("❌ Rate limit exceeded. Please try again later.")
        return None
    except openai.APIError as e:
        st.error(f"❌ OpenAI API error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Transcription failed: {str(e)}")
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

def real_generate_mom(prompt, api_key):
    """Real MoM generation using OpenAI GPT API"""
    try:
        # Set up OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Show progress during generation
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🤖 Starting MoM generation...")
        progress_bar.progress(20)
        
        status_text.text("📝 Analyzing meeting content...")
        progress_bar.progress(40)
        
        # Call OpenAI GPT API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You can also use "gpt-4" for better results
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional meeting secretary who creates clear, comprehensive Minutes of Meeting documents. Always format output in markdown for better readability."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2000,
            temperature=0.3  # Lower temperature for more consistent, professional output
        )
        
        progress_bar.progress(80)
        status_text.text("🎯 Formatting final document...")
        
        # Extract the generated MoM
        generated_mom = response.choices[0].message.content
        
        progress_bar.progress(100)
        status_text.text("✅ Generation complete!")
        time.sleep(0.5)  # Brief pause to show completion
        
        return generated_mom
        
    except openai.AuthenticationError:
        st.error("❌ Invalid OpenAI API key. Please check your API key.")
        return None
    except openai.RateLimitError:
        st.error("❌ Rate limit exceeded. Please try again later.")
        return None
    except openai.APIError as e:
        st.error(f"❌ OpenAI API error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ MoM generation failed: {str(e)}")
        return None

# Demo transcript data (kept as fallback)
DEMO_TRANSCRIPT = [
    {"start_time": 0, "end_time": 15, "text": "Good morning everyone. Thank you for joining today's project review meeting. I'm Sarah from the product team."},
    {"start_time": 15, "end_time": 35, "text": "Today we'll be discussing the Q2 roadmap, current sprint progress, and addressing the client feedback from last week."},
    {"start_time": 35, "end_time": 55, "text": "Mike, can you start us off with the development update? How are we tracking against our sprint goals?"},
    {"start_time": 55, "end_time": 85, "text": "Sure Sarah. We've completed 8 out of 10 user stories this sprint. The remaining two are the authentication module and the reporting dashboard."},
    {"start_time": 85, "end_time": 110, "text": "The authentication is 90% done, just pending security review. The dashboard needs another 3 days of work."},
    {"start_time": 110, "end_time": 140, "text": "That's great progress Mike. Lisa, what's the feedback from the client demo last Friday?"},
    {"start_time": 140, "end_time": 170, "text": "The client loved the new UI improvements. They specifically mentioned the faster load times and cleaner interface."},
    {"start_time": 170, "end_time": 200, "text": "However, they requested two new features: bulk data import and email notifications for critical alerts."},
    {"start_time": 200, "end_time": 230, "text": "I think we can accommodate the email notifications in the current sprint, but bulk import might need to go to next sprint."},
    {"start_time": 230, "end_time": 260, "text": "Agreed. Let's prioritize the email notifications. Tom, can you handle the technical specification for that?"},
    {"start_time": 260, "end_time": 290, "text": "Absolutely. I'll have the tech spec ready by Wednesday and we can review it in Thursday's standup."},
    {"start_time": 290, "end_time": 320, "text": "Perfect. Any other concerns or blockers? We have the budget review next week so we need to finalize our Q3 estimates."},
    {"start_time": 320, "end_time": 350, "text": "I'll prepare the development effort estimates and send them to Sarah by end of day tomorrow."},
    {"start_time": 350, "end_time": 370, "text": "Great. Let's wrap up. Thanks everyone for the productive meeting. Next review is scheduled for Friday."}
]

# Main App Interface
st.markdown("<h1 class='main-header'>🤖 AI MoM Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Transform meeting recordings into professional Minutes of Meeting with AI</p>", unsafe_allow_html=True)

# Sidebar for API Configuration
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # API Key Input
    api_key = st.text_input(
        "OpenAI API Key", 
        type="password", 
        help="Enter your OpenAI API key to enable real transcription and MoM generation"
    )
    
    if api_key:
        # Test API key validity
        try:
            test_client = openai.OpenAI(api_key=api_key)
            # Simple test call to validate key
            test_response = test_client.models.list()
            st.session_state.api_key_set = True
            st.success("✅ API Key Valid")
        except:
            st.error("❌ Invalid API Key")
            st.session_state.api_key_set = False
    else:
        st.warning("⚠️ Enter API key for real functionality")
        st.session_state.api_key_set = False
    
    if not api_key:
        st.info("💡 Demo mode available with sample data")
    
    st.markdown("---")
    st.markdown("### 💰 API Usage Costs")
    st.markdown("""
    **Whisper API:** ~$0.006/minute
    **GPT-3.5-turbo:** ~$0.002/1K tokens
    **GPT-4:** ~$0.06/1K tokens
    
    *Typical 30-min meeting: ~$0.20-$2.00*
    """)
    
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
    1. **Enter API Key** above
    2. **Upload/Record** audio file
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
        progress_items.append("✅ API Key valid")
    else:
        progress_items.append("⏳ Enter API Key")
    
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
    
    # Quick test button
    if st.button("🧪 Quick Test Setup"):
        st.session_state.transcript_data = DEMO_TRANSCRIPT
        st.session_state.selected_transcript = "\n".join([f"[{format_time(s['start_time'])} - {format_time(s['end_time'])}] {s['text']}" for s in DEMO_TRANSCRIPT])
        st.session_state.config = {
            'context': 'Sprint review meeting to discuss development progress, client feedback, and next steps.',
            'previous_meeting': '',
            'audience': 'Project Team',
            'goal': 'Review progress and plan next sprint',
            'tone': 'Action-focused'
        }
        st.success("✅ Quick test setup complete!")
        st.rerun()

# Main content area with tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎤 Audio Input", "📝 Transcript", "⚙️ Configuration", "✨ Generate MoM", "📥 Export"])

with tab1:
    st.markdown("<h3 class='section-header'>Audio Input</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Upload Audio File")
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['mp3', 'wav', 'm4a', 'ogg', 'mp4', 'mpeg', 'mpga', 'webm'],
            help="Upload meeting recording. Supported: MP3, WAV, M4A, OGG, MP4, MPEG, MPGA, WEBM"
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
            
            # Check file size limit (OpenAI has 25MB limit)
            if uploaded_file.size > 25 * 1024 * 1024:
                st.error("❌ File too large! OpenAI Whisper has a 25MB limit. Please compress your audio file.")
            else:
                st.audio(uploaded_file)
                
                # Transcription button
                if st.session_state.api_key_set:
                    transcribe_button = st.button("🔄 Transcribe Audio with OpenAI Whisper", type="primary", key="transcribe_btn")
                    
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
                                result = real_transcribe_audio(uploaded_file, api_key)
                                
                                if result:
                                    st.session_state.transcript_data = result
                                    
                                    # Success message
                                    st.success("✅ Transcription completed successfully!")
                                    st.balloons()
                                    
                                    # Show transcript stats
                                    st.info(f"📊 Generated {len(result)} transcript segments")
                                    
                                    # Auto-advance to transcript tab
                                    st.info("👉 Check the 'Transcript' tab to review your transcription!")
                                else:
                                    st.error("❌ Transcription failed. Please check your API key and try again.")
                                    
                        except Exception as e:
                            st.error(f"❌ Transcription failed: {str(e)}")
                            st.error("Please check your API key and try again.")
                else:
                    st.warning("⚠️ Please enter a valid OpenAI API key to use real transcription")
                    st.info("💡 You can use the demo data button below for testing")
        
        else:
            st.info("👆 Please upload an audio file to start transcription")
        
        # Demo data option
        st.markdown("---")
        st.markdown("#### 🧪 Demo Mode")
        demo_button = st.button("📊 Load Demo Transcript", help="Load sample meeting transcript for testing")
        
        if demo_button:
            st.session_state.transcript_data = DEMO_TRANSCRIPT
            st.success("✅ Demo transcript loaded!")
            st.info("👉 Go to the 'Transcript' tab to see the demo data!")
            st.balloons()
    
    with col2:
        st.markdown("#### 🎙️ Record Audio")
        
        # Audio recording interface (placeholder for now)
        st.info("🚧 **Live Recording Feature**")
        st.markdown("""
        **Status:** Available in full production version
        
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
                st.info("Feature available in production version")
        with col_rec2:
            if st.button("⏹️ Stop Recording", disabled=True):
                st.info("Would stop recording and auto-transcribe")
        
        # Recording implementation guide
        with st.expander("🔧 Implementation Guide"):
            st.code("""
# To enable real recording, install:
pip install streamlit-webrtc

# Then add this code:
from streamlit_webrtc import webrtc_streamer
import av

def audio_frame_callback(frame):
    # Process audio frames
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
        
        st.markdown("---")
        st.markdown("**💡 Current Options:**")
        st.markdown("- 📁 Audio file upload ✅ **REAL API**")
        st.markdown("- 📊 Demo transcript (for testing)")
        st.markdown("- 🎵 Upload any audio format")
        st.markdown("- 🤖 Real OpenAI Whisper transcription")

with tab2:
    st.markdown("<h3 class='section-header'>Transcript Review</h3>", unsafe_allow_html=True)
    
    if st.session_state.transcript_data:
        st.success(f"✅ Transcript loaded with {len(st.session_state.transcript_data)} segments")
        
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
            
            # Show word count and estimated cost
            word_count = len(selected_text.split())
            estimated_tokens = word_count * 1.3  # Rough estimate
            estimated_cost = estimated_tokens / 1000 * 0.002  # GPT-3.5-turbo pricing
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Words Selected", word_count)
            with col2:
                st.metric("Est. Tokens", f"{estimated_tokens:.0f}")
            with col3:
                st.metric("Est. Cost", f"${estimated_cost:.4f}")
        else:
            st.warning("⚠️ No segments selected in this time range")
    else:
        st.info("👆 Please upload an audio file or load demo data in the Audio Input tab")

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
            "OpenAI Model",
            ["gpt-3.5-turbo", "gpt-4"],
            help="GPT-4 provides better quality but costs more"
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
    
    if st.session_state.selected_transcript and hasattr(st.session_state, 'config'):
        config = st.session_state.config
        
        # Show summary of configuration
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Audience", config['audience'])
        with col2:
            st.metric("Tone", config['tone'])
        with col3:
            st.metric("Model", config.get('model', 'gpt-3.5-turbo'))
        with col4:
            st.metric("Transcript Length", f"{len(st.session_state.selected_transcript.split())} words")
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            custom_instructions = st.text_area(
                "Additional Instructions",
                placeholder="e.g., Focus on action items, include budget discussions, emphasize deadlines...",
                help="Any specific instructions for the AI to follow"
            )
            
            include_timestamps = st.checkbox("Include Timestamps", value=True)
            include_sentiment = st.checkbox("Include Sentiment Analysis", value=False)
        
        # Generate MoM
        if st.session_state.api_key_set:
            generate_button = st.button("✨ Generate Minutes of Meeting with OpenAI", type="primary", key="generate_mom_btn")
            
            if generate_button:
                if not config['context']:
                    st.error("❌ Please provide meeting context in the Configuration tab")
                else:
                    # Create containers for the generation process
                    generation_container = st.container()
                    
                    with generation_container:
                        st.info("🚀 Starting real MoM generation with OpenAI...")
                        
                        prompt = generate_mom_prompt(
                            st.session_state.selected_transcript,
                            config['context'],
                            config['previous_meeting'],
                            config['tone'],
                            config['audience'],
                            config['goal']
                        )
                        
                        # Add custom instructions if provided
                        if custom_instructions:
                            prompt += f"\n\nADDITIONAL
