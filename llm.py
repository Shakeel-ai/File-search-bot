import json
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import os
import streamlit as st
from streamlit_chat import message

st.set_page_config(page_title='Talking with books')
st.title('Document_GPT:white_check_mark:')

# Load environment variables from .env file
load_dotenv(find_dotenv())
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# File path to store assistant and vector store IDs
ids_file_path = 'ids.json'

def load_ids():
    try:
        with open(ids_file_path, 'r') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        return {"assistant_id": None, "vector_store_id": None}
    except json.JSONDecodeError as e:
        return {"assistant_id": None, "vector_store_id": None}, (f"Error decoding JSON from ids file: {e}")

def save_ids(assistant_id, vector_store_id):
    with open(ids_file_path, 'w') as f:
        json.dump({"assistant_id": assistant_id, "vector_store_id": vector_store_id}, f)

def create_new_assistant_and_vector_store(file):
    assistant = client.beta.assistants.create(
        name='Pdf_Bot',
        instructions=(
            'You are a Document GPT . Introduce yourself to users politely in the first message. '
            'Your task is to assist users with answer their queries . If the response is not in the document, respond from your knowledge.'
        ),
        model='gpt-3.5-turbo',
        tools=[{"type": 'file_search'}]
    )
    assistant_id = assistant.id
    
    vector_store = client.beta.vector_stores.create()
    vector_store_id = vector_store.id

    client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store_id, files=file
    )

    client.beta.assistants.update(
        assistant_id=assistant_id, 
        tool_resources={'file_search': {'vector_store_ids': [vector_store_id]}}
    )

    save_ids(assistant_id, vector_store_id)
    return assistant_id, vector_store_id

def get_response(user_input, thread_id):
    try:
        data = load_ids()
        assistant_id = data.get('assistant_id')
        if not assistant_id:
            st.error("Please train your bot first")
            st.stop()
        
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role='user',
            content=user_input
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id, assistant_id=assistant_id
        )

        messages = list(client.beta.threads.messages.list(thread_id=thread_id, run_id=run.id))
        message_content = messages[0].content[0].text.value  # Directly access the value attribute
        response = message_content
    except Exception as e:
        return f"Error: {e}"
    
    return response

if __name__ == '__main__':
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = ""
    if 'process_complete' not in st.session_state:
        st.session_state.process_complete = False
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []    

    with st.sidebar:
        st.header("Train Your Bot")
        file = st.file_uploader('Upload Your File', type=['pdf', 'docx'], accept_multiple_files=True)       
        if st.button('Process'):  
            if file is None:
                st.error("Please upload a file")
                st.stop()
            else:    
                assistant_id, vector_store_id = create_new_assistant_and_vector_store(file)
                st.session_state.process_complete = True
                st.success("Training completed successfully.")
        st.header("If Alraedy Train")    
        if st.button('Start'):
            st.session_state.process_complete = True

        
    if st.session_state.thread_id == "":
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id    
    
    thread_id = st.session_state.thread_id
    
    if st.session_state.process_complete:
        user_input = st.chat_input('Ask Your Question') 
    
        with st.container():
            with st.spinner("Thinking"):
                if user_input:
                    response, thread_id = get_response(user_input, thread_id)
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                for i, messages in enumerate(st.session_state.chat_history):
                    if messages['role'] == 'user':
                        message(messages['content'], is_user=True, key=str(i),is_table=True)
                    else:
                        message(messages['content'], key=str(i),is_table=True)
