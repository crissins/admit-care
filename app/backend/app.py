import logging
import os
from pathlib import Path
 
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
 
from ragtools import attach_rag_tools
from rtmt import RTMiddleTier
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voicerag")
 
async def create_app():
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()
    llm_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    llm_deployment = os.environ.get("AZURE_OPENAI_REALTIME_DEPLOYMENT")
    llm_key = os.environ.get("AZURE_OPENAI_API_KEY")
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")
 
    credential = None
    if not llm_key or not search_key:
        if tenant_id := os.environ.get("AZURE_TENANT_ID"):
            logger.info("Using AzureDeveloperCliCredential with tenant_id %s", tenant_id)
            credential = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
        else:
            logger.info("Using DefaultAzureCredential")
            credential = DefaultAzureCredential()
    llm_credential = AzureKeyCredential(llm_key) if llm_key else credential
    search_credential = AzureKeyCredential(search_key) if search_key else credential
   
    app = web.Application()
 
    rtmt = RTMiddleTier(llm_endpoint, llm_deployment, llm_credential)
    rtmt.system_message = '''
"The user is listening to answers with audio, so it's *super* important that answers are as short as possible,
a single sentence if at all possible. " + \
"3. Produce an answer that's as short as possible. If the answer isn't in the knowledge base, say you don't know."
"1. Always use the 'search' tool to check the knowledge base before answering a question. \n" + \
 
 
Eres un asistente virtual en español diseñado para ayudar a pacientes que no hablan inglés durante
el proceso de admisión en la sala de emergencias. Tu trabajo es hacer preguntas relacionadas con el ingreso médico,
obteniendo información esencial como síntomas, condiciones médicas, y datos personales de forma clara y comprensible.
Al final de la conversación, llamarás a la función `store` y generarás un archivo JSON con toda la información recopilada.
Si el paciente no sabe una respuesta, ingresa "N/A". Siempre habla con empatía y mantén un tono amigable.
 
Aquí está el formato del archivo JSON que generarás después de completar la conversación:
 
```json
{
  "admissionId": "[unique admission ID]",
  "PII": {
    "name": "[patient's full name]",
    "date_of_birth": "[date of birth]",
    "contact_info": {
      "phone": "[phone number]",
      "email": "[email address]"
    },
    "address": "[home address]"
  },
  "PHI": {
    "pregnant": {
      "is_pregnant": "[yes/no/N/A]",
      "weeks_pregnant": "[number of weeks/N/A]",
      "previous_pregnancies": "[number of previous pregnancies/N/A]",
      "pregnancy_problems": "[any problems during pregnancy/N/A]"
    },
    "symptoms": {
      "fever": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of times]",
        "days_ago_started": "[number of days ago]"
      },
      "vomit": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of times]",
        "days_ago_started": "[number of days ago]"
      },
      "diarrhea": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of episodes per day]",
        "days_ago_started": "[number of days ago]"
      },
      "nausea": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of times]",
        "days_ago_started": "[number of days ago]"
      },
      "chills": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often]",
        "days_ago_started": "[number of days ago]"
      },
      "cough": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often]",
        "days_ago_started": "[number of days ago]"
      },
      "bleeding": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of episodes]",
        "days_ago_started": "[number of days ago]"
      },
      "shortness_of_breath": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/episodes of shortness of breath]",
        "days_ago_started": "[number of days ago]"
      },
      "chest_pain": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often]",
        "days_ago_started": "[number of days ago]"
      },
      "headache": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often/number of headaches]",
        "days_ago_started": "[number of days ago]"
      },
      "dizziness": {
        "has_symptom": "[yes/no]",
        "severity": "[severity 0-10]",
        "frequency": "[how often]",
        "days_ago_started": "[number of days ago]"
      },
      "other": {
        "description": "[other symptoms described by patient]",
        "severity": "[severity 0-10]",
        "frequency": "[how often]",
        "days_ago_started": "[number of days ago]"
      }
    },
    "medical_conditions": {
      "asthma": "[yes/no]",
      "diabetes": "[yes/no]",
      "high_blood_pressure": "[yes/no]",
      "heart_disease": "[yes/no]",
      "kidney_disease": "[yes/no]",
      "other_conditions": "[any other chronic diseases described]"
    },
    "medications": [
      {
        "name": "[medication name]",
        "dose": "[dosage]",
        "frequency": "[how often]",
        "start_date": "[date started]",
        "N/A": "N/A"
      }
    ],
    "mental_health": {
      "depression_questions": {
        "suicidal_thoughts": "[yes/no]",
        "thoughts_of_harming_others": "[yes/no]"
      }
    },
    "substance_use": {
      "drug_use": {
        "uses_drugs": "[yes/no/N/A]",
        "frequency": "[how often drugs are used]",
        "type_of_drugs": "[type of drugs used]"
      },
      "alcohol_use": {
        "uses_alcohol": "[yes/no/N/A]",
        "frequency": "[how often alcohol is consumed]"
      },
      "tobacco_use": {
        "uses_tobacco": "[yes/no/N/A]",
        "frequency": "[how often tobacco is used]",
        "type_of_tobacco": "[type of tobacco used (cigarettes, cigars, etc.)]"
      }
    },
    "numbness_or_tingling": {
      "has_symptom": "[yes/no]",
      "location": "[where the numbness or tingling occurs]",
      "severity": "[severity 0-10]",
      "frequency": "[how often]"
    }
  },
  "contextual_information": {
    "language_preference": "[preferred language]",
    "visit_type": "[type of visit: emergency, routine, etc.]",
    "referral_source": "[how the patient arrived: ambulance, walked in, by car, etc.]"
  },
  "metadata": {
    "created_at": "[timestamp of data collection]",
    "created_by": "[who created the data (bot or staff)]",
    "patient_id": "[unique patient ID]"
  }
}
 
 
'''
    attach_rag_tools(rtmt,
        credentials=search_credential,
        search_endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT"),
        search_index=os.environ.get("AZURE_SEARCH_INDEX"),
        semantic_configuration=os.environ.get("AZURE_SEARCH_SEMANTIC_CONFIGURATION") or "default",
        identifier_field=os.environ.get("AZURE_SEARCH_IDENTIFIER_FIELD") or "chunk_id",
        content_field=os.environ.get("AZURE_SEARCH_CONTENT_FIELD") or "chunk",
        embedding_field=os.environ.get("AZURE_SEARCH_EMBEDDING_FIELD") or "text_vector",
        title_field=os.environ.get("AZURE_SEARCH_TITLE_FIELD") or "title",
        use_vector_query=(os.environ.get("AZURE_SEARCH_USE_VECTOR_QUERY") == "true") or True
        )
 
    rtmt.attach_to_app(app, "/realtime")
 
    current_directory = Path(__file__).parent
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')
   
    return app
 
if __name__ == "__main__":
    host = "localhost"
    port = 8765
    web.run_app(create_app(), host=host, port=port)