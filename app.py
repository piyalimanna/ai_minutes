import streamlit as st
import openai
import json
import io
import base64
from datetime import datetime, timedelta
import re
import time

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

# Mock transcript data for demo purposes
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

def format_time(seconds):
    """Convert seconds to MM:SS format"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

def mock_transcribe_audio(audio_file):
    """Mock transcription function - in real app, this would call OpenAI Whisper"""
    # Show that we're processing the actual file
    st.info(f"📁 Processing file: {audio_file.name} ({audio_file.size} bytes)")
    
    # Simulate processing time based on file size
    processing_time = min(5, max(2, audio_file.size / 1000000))  # 2-5 seconds based on file size
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(100):
        time.sleep(processing_time / 100)
        progress_bar.progress(i + 1)
        if i < 30:
            status_text.text("🎵 Analyzing audio format...")
        elif i < 60:
            status_text.text("🔊 Processing audio segments...")
        elif i < 90:
            status_text.text("🤖 Generating transcript...")
        else:
            status_text.text("✨ Finalizing results...")
    
    status_text.text("✅ Transcription complete!")
    time.sleep(0.5)  # Brief pause to show completion
    
    return DEMO_TRANSCRIPT

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
"""
    
    return prompt

def mock_generate_mom(prompt):
    """Mock MoM generation - in real app, this would call OpenAI GPT"""
    
    # Show progress during generation
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    steps = [
        "🤖 Analyzing meeting transcript...",
        "📝 Extracting key discussion points...",
        "🎯 Identifying action items...",
        "📋 Structuring meeting summary...",
        "✨ Formatting final document..."
    ]
    
    for i, step in enumerate(steps):
        status_text.text(step)
        progress_bar.progress((i + 1) * 20)
        time.sleep(0.8)  # Slightly faster for better UX
    
    status_text.text("✅ Generation complete!")
    time.sleep(0.3)
    
    # This is a mock response - in real app, you'd call OpenAI API
    mock_response = """
# Minutes of Meeting - Project Review

**Date:** June 15, 2025  
**Duration:** 6 minutes 10 seconds  
**Attendees:** Sarah (Product Team), Mike (Development), Lisa (Client Relations), Tom (Technical Lead)  
**Meeting Type:** Project Review and Planning  

## Meeting Overview
Quarterly project review focusing on Q2 roadmap progress, sprint status, and client feedback integration.

## Key Discussion Points

### Sprint Progress Update
- **Current Status:** 8 out of 10 user stories completed (80% completion rate)
- **Pending Items:** 
  - Authentication module (90% complete, pending security review)
  - Reporting dashboard (3 days of work remaining)

### Client Feedback Summary
- **Positive Reception:** UI improvements well-received, particularly load time optimization and interface design
- **New Requirements:** 
  - Bulk data import functionality
  - Email notifications for critical alerts

### Resource Allocation
- Email notifications approved for current sprint
- Bulk import deferred to next sprint due to complexity

## Decisions Made
1. **Prioritization:** Email notifications take precedence over bulk import
2. **Sprint Scope:** Authentication and dashboard completion remains priority
3. **Q3 Planning:** Budget review scheduled for next week

## Action Items
| Task | Owner | Deadline | Status |
|------|-------|----------|--------|
| Complete authentication security review | Mike | This Sprint | In Progress |
| Finish reporting dashboard | Mike | 3 days | Pending |
| Technical specification for email notifications | Tom | Wednesday | Assigned |
| Review email notification spec | Team | Thursday Standup | Scheduled |
| Prepare Q3 development estimates | Mike | Tomorrow EOD | Assigned |

## Next Steps
- Thursday standup: Review email notification technical specification
- Friday: Next project review meeting
- Next week: Budget review and Q3 planning finalization

## Meeting Outcome
Productive session with clear progress tracking and realistic timeline adjustments. Client requirements successfully integrated into sprint planning.

---
*Generated by AI MoM Assistant*
"""
    
    return mock_response

# Main App Interface
st.markdown("<h1 class='main-header'>🤖 AI MoM Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Transform meeting recordings into professional Minutes of Meeting with AI</p>", unsafe_allow_html=True)

# Sidebar for API Configuration
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # API Key Input (for demo, we'll use mock functions)
    api_key = st.text_input("OpenAI API Key", type="password", help="Enter your OpenAI API key")
    if api_key:
        st.session_state.api_key_set = True
        st.success("✅ API Key Set")
    else:
        st.info("💡 Using demo mode with mock data")
    
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
    1. **Upload/Record** audio file
    2. **Review** transcript segments
    3. **Select** time range
    4. **Configure** context & tone
    5. **Generate** MoM
    6. **Export** results
    """)

# Main content area with tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎤 Audio Input", "📝 Transcript", "⚙️ Configuration", "✨ Generate MoM", "📥 Export"])

with tab1:
    st.markdown("<h3 class='section-header'>Audio Input</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Upload Audio File")
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['mp3', 'wav', 'm4a', 'ogg'],
            help="Upload meeting recording in MP3, WAV, M4A, or OGG format"
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
            
            st.audio(uploaded_file)
            
            # Transcription button with better state management
            transcribe_button = st.button("🔄 Transcribe Audio", type="primary", key="transcribe_btn")
            
            if transcribe_button:
                try:
                    # Clear any previous transcript
                    if 'transcript_data' in st.session_state:
                        del st.session_state.transcript_data
                    
                    # Create a container for the transcription process
                    transcription_container = st.container()
                    
                    with transcription_container:
                        st.info("🎯 Starting transcription process...")
                        
                        # Call the mock transcription function
                        st.session_state.transcript_data = mock_transcribe_audio(uploaded_file)
                        
                        # Success message
                        st.success("✅ Transcription completed successfully!")
                        st.balloons()
                        
                        # Auto-advance to transcript tab
                        st.info("👉 Check the 'Transcript' tab to review your transcription!")
                        
                except Exception as e:
                    st.error(f"❌ Transcription failed: {str(e)}")
                    st.error("Please try uploading the file again or use the demo data.")
        
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
        st.info("🚧 Voice recording feature would be implemented using streamlit-webrtc in production")
        st.markdown("""
        **In the full version:**
        - Real-time voice recording
        - Audio quality controls
        - Recording duration limits
        - Pause/resume functionality
        """)

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
        
        # Store configuration in session state
        st.session_state.config = {
            'context': meeting_context,
            'previous_meeting': previous_meeting,
            'audience': audience,
            'goal': meeting_goal,
            'tone': tone
        }

with tab4:
    st.markdown("<h3 class='section-header'>Generate Minutes of Meeting</h3>", unsafe_allow_html=True)
    
    if st.session_state.selected_transcript and hasattr(st.session_state, 'config'):
        config = st.session_state.config
        
        # Show summary of configuration
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Audience", config['audience'])
        with col2:
            st.metric("Tone", config['tone'])
        with col3:
            st.metric("Transcript Length", f"{len(st.session_state.selected_transcript.split())} words")
        
        st.markdown("#### 🔧 Final Prompt Configuration")
        
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
        generate_button = st.button("✨ Generate Minutes of Meeting", type="primary", key="generate_mom_btn")
        
        if generate_button:
            if not config['context']:
                st.error("❌ Please provide meeting context in the Configuration tab")
            else:
                # Create containers for the generation process
                generation_container = st.container()
                
                with generation_container:
                    st.info("🚀 Starting MoM generation...")
                    
                    prompt = generate_mom_prompt(
                        st.session_state.selected_transcript,
                        config['context'],
                        config['previous_meeting'],
                        config['tone'],
                        config['audience'],
                        config['goal']
                    )
                    
                    # Show progress during generation
                    progress_container = st.container()
                    with progress_container:
                        st.session_state.generated_mom = mock_generate_mom(prompt)
                    
                    st.success("✅ Minutes of Meeting generated successfully!")
                    st.balloons()
                    
                    # Force immediate display of results
                    st.markdown("#### 📋 Your Generated Minutes of Meeting")
                    st.markdown("---")
        
        # Always show generated MoM if it exists
        if st.session_state.generated_mom:
            st.markdown("#### 📋 Generated Minutes of Meeting")
            
            # Create a nice container for the MoM
            mom_container = st.container()
            with mom_container:
                st.markdown(f"""
                <div class='mom-output'>
{st.session_state.generated_mom}
                </div>
                """, unsafe_allow_html=True)
                
                # Add a copy button for convenience
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.markdown("**Quick Actions:**")
                    if st.button("📋 Copy Text", key="quick_copy"):
                        st.info("💡 Text is displayed above - select and copy!")
                    if st.button("📥 Go to Export", key="go_to_export"):
                        st.info("👉 Check the 'Export' tab for download options!")
            
            # Refinement options
            st.markdown("#### 🔄 Refine Results")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📝 Make More Detailed"):
                    st.info("🔄 Regenerating with more detail...")
                    # In real app, modify prompt and regenerate
                
                if st.button("⚡ Make More Concise"):
                    st.info("🔄 Regenerating more concisely...")
                    # In real app, modify prompt and regenerate
            
            with col2:
                if st.button("🎯 Focus on Action Items"):
                    st.info("🔄 Regenerating with action item focus...")
                    # In real app, modify prompt and regenerate
                
                if st.button("📊 Add More Analysis"):
                    st.info("🔄 Adding analytical insights...")
                    # In real app, modify prompt and regenerate
    
    else:
        if not st.session_state.selected_transcript:
            st.info("👆 Please select a transcript segment in the Transcript tab")
        else:
            st.info("👆 Please configure meeting details in the Configuration tab")

with tab5:
    st.markdown("<h3 class='section-header'>Export Results</h3>", unsafe_allow_html=True)
    
    if st.session_state.generated_mom:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📋 Copy to Clipboard")
            st.text_area(
                "Generated MoM (Copy this text)",
                value=st.session_state.generated_mom,
                height=200,
                help="Select all text and copy to clipboard"
            )
        
        with col2:
            st.markdown("#### 💾 Download Options")
            
            # Text download
            st.download_button(
                label="📄 Download as TXT",
                data=st.session_state.generated_mom,
                file_name=f"meeting_minutes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
            
            # Markdown download
            st.download_button(
                label="📝 Download as Markdown",
                data=st.session_state.generated_mom,
                file_name=f"meeting_minutes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
            
            st.markdown("---")
            st.markdown("#### 🔮 Future Export Options")
            st.info("""
            **Coming in V2:**
            - 📑 PDF export with formatting
            - 📧 Email integration
            - 📱 Mobile sharing
            - 🔗 Calendar integration
            - 📊 Analytics dashboard
            """)
        
        # Usage statistics
        st.markdown("---")
        st.markdown("#### 📊 Session Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            word_count = len(st.session_state.generated_mom.split())
            st.metric("Words Generated", word_count)
        
        with col2:
            if st.session_state.transcript_data:
                transcript_duration = st.session_state.transcript_data[-1]['end_time']
                st.metric("Meeting Duration", f"{format_time(transcript_duration)}")
            else:
                st.metric("Meeting Duration", "N/A")
        
        with col3:
            if st.session_state.selected_transcript:
                selected_words = len(st.session_state.selected_transcript.split())
                st.metric("Transcript Words", selected_words)
            else:
                st.metric("Transcript Words", "N/A")
        
        with col4:
            compression_ratio = round(word_count / len(st.session_state.selected_transcript.split()) * 100, 1) if st.session_state.selected_transcript else 0
            st.metric("Compression Ratio", f"{compression_ratio}%")
    
    else:
        st.info("👆 Generate a MoM first to see export options")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <h4>🚀 AI MoM Assistant - Demo Version</h4>
    <p>Transform your meeting recordings into professional documentation with AI</p>
    <p><strong>Tech Stack:</strong> Streamlit • OpenAI Whisper • GPT-3.5 • Python</p>
    <p><em>Built for demonstration purposes - Ready for production deployment</em></p>
</div>
""", unsafe_allow_html=True)
