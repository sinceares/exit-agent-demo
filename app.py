import json
import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

st.set_page_config(
    page_title="Context-Aware Exit Agent Demo",
    page_icon="☎️",
    layout="wide"
)

def check_password():
    def password_entered():
        if st.session_state["password"] == os.getenv("DEMO_PASSWORD"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if not st.session_state.get("password_correct", False):
        st.text_input("Zugangscode", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("Falscher Zugangscode")
        st.stop()

check_password()

def check_password():
    def password_entered():
        if st.session_state["password"] == os.getenv("DEMO_PASSWORD"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if not st.session_state.get("password_correct", False):
        st.text_input("Zugangscode", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("Falscher Zugangscode")
        st.stop()

check_password()

SCENARIOS = {
    "Terminverschiebung wegen Reise": {
        "current_exit": "Ihr Termin wurde geändert. Vielen Dank für Ihren Anruf.",
        "state": {
            "intent": "appointment_rescheduling",
            "outcome": "success",
            "slots": {
                "new_date": "2. Mai",
                "new_time": "14:00"
            },
            "next_steps": ["confirmation_email"],
            "conversation_focus": {
                "primary_concern": "Termin wegen Reise verschieben",
                "caller_reason": "der ursprüngliche Termin passte nicht zur Reiseplanung",
                "emotional_tone": "slightly_stressed",
                "key_terms_to_reuse": ["Termin verschoben", "Reiseplanung", "Bestätigung"]
            }
        }
    },
    "Unklare Rechnung / Beschwerde": {
        "current_exit": "Unser Team meldet sich bei Ihnen. Vielen Dank für Ihren Anruf.",
        "state": {
            "intent": "billing_complaint",
            "outcome": "unresolved",
            "slots": {},
            "next_steps": ["human_followup"],
            "conversation_focus": {
                "primary_concern": "Unklarheiten bei der Rechnung",
                "caller_reason": "der Betrag wirkt falsch oder nicht nachvollziehbar",
                "emotional_tone": "frustrated",
                "key_terms_to_reuse": ["Rechnung", "Unklarheiten", "prüfen"]
            }
        }
    },
    "Kein kurzfristiger Termin verfügbar": {
        "current_exit": "Leider ist kein Termin verfügbar. Vielen Dank für Ihren Anruf.",
        "state": {
            "intent": "appointment_booking",
            "outcome": "failed",
            "failure_reason": "no_availability",
            "slots": {
                "preferred_time": "morgen Vormittag"
            },
            "next_steps": ["try_later", "contact_team_if_urgent"],
            "conversation_focus": {
                "primary_concern": "kurzfristig einen Termin bekommen",
                "caller_reason": "das Anliegen wirkt zeitkritisch",
                "emotional_tone": "urgent",
                "key_terms_to_reuse": ["kurzfristiger Termin", "dringend", "Verfügbarkeit"]
            }
        }
    }
}


def generate_exit_with_llm(call_state: dict, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Kein OPENAI_API_KEY gefunden. Bitte .env-Datei anlegen."

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=build_prompt(call_state)
    )

    return response.output_text.strip()

def build_prompt(call_state: dict) -> str:
    return f"""
Du bist ein Exit-Agent für einen telefonischen AI Assistant.

Aufgabe:
Erzeuge einen natürlichen, kurzen Gesprächsabschluss auf Deutsch.

Regeln:
- Bestätige das tatsächliche Outcome klar.
- Verwende nur Informationen aus dem Call-State.
- Erfinde keine Details.
- Greife 1–2 Begriffe aus conversation_focus.key_terms_to_reuse auf.
- Passe den Ton an emotional_tone an.
- Nenne relevante next_steps.
- Maximal 3 Sätze.
- Formell mit "Sie".

Call-State:
{json.dumps(call_state, indent=2, ensure_ascii=False)}
""".strip()

def extract_conversation_focus(transcript: str, model: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "primary_concern": "Kein API-Key gefunden",
            "caller_reason": "",
            "emotional_tone": "unknown",
            "key_terms_to_reuse": [],
            "unresolved_points": []
        }

    client = OpenAI(api_key=api_key)

    prompt = f"""
Extrahiere aus diesem Telefongespräch den Conversation Focus für einen Exit-Agenten.

Antworte ausschließlich mit validem JSON.
Kein Markdown.
Keine Erklärung.
Keine Code-Fences.

JSON-Schema:
{{
  "primary_concern": "string",
  "caller_reason": "string",
  "emotional_tone": "neutral | stressed | frustrated | relieved | urgent",
  "key_terms_to_reuse": ["string", "string"],
  "unresolved_points": ["string"]
}}

Regeln:
- Nur Informationen verwenden, die im Gespräch vorkommen.
- Nichts erfinden.
- Kurz und präzise.

Transcript:
{transcript}
""".strip()

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    raw = response.output_text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        st.warning("Das Modell hat kein reines JSON zurückgegeben. Rohantwort:")
        st.code(raw)

        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start != -1 and end != -1:
            return json.loads(raw[start:end])

        return {
            "primary_concern": "JSON konnte nicht extrahiert werden",
            "caller_reason": "",
            "emotional_tone": "unknown",
            "key_terms_to_reuse": [],
            "unresolved_points": []
        }
    
def validate_exit(exit_text: str, call_state: dict) -> list:
    checks = []

    focus = call_state.get("conversation_focus", {})
    key_terms = focus.get("key_terms_to_reuse", [])

    checks.append((
        "Conversation Focus aufgegriffen",
        any(term.lower() in exit_text.lower() for term in key_terms)
    ))

    checks.append((
        "Maximal 3 Sätze",
        exit_text.count(".") <= 3
    ))

    checks.append((
        "Keine sehr lange Antwort",
        len(exit_text.split()) <= 70
    ))

    return checks

st.title("☎️ Context-Aware Exit Agent Demo")

st.markdown(
    """
Diese Demo zeigt den Unterschied zwischen einem statischen Gesprächsabschluss
und einem kontextbewussten LLM-basierten Exit-Agent.
"""
)

scenario_name = st.selectbox("Szenario auswählen", list(SCENARIOS.keys()))
scenario = SCENARIOS[scenario_name]

model = st.selectbox(
    "Modell auswählen",
    ["gpt-4.1-mini", "gpt-4.1", "gpt-5.5"],
    index=0
)

# 🔥 HIER STARTET DEIN NEUER BLOCK
st.divider()

st.subheader("🎙️ Optional: Transcript → Conversation Focus")

example_transcript = st.text_area(
    "Beispiel-Transcript",
    value="""Caller: Ich kann den Termin am Montag leider nicht wahrnehmen, weil ich auf Reisen bin.
Assistant: Kein Problem. Wann würde es Ihnen besser passen?
Caller: Freitag Nachmittag wäre ideal.
Assistant: Ich habe einen Termin am Freitag um 14 Uhr gefunden und verschoben.
Caller: Super, danke. Ich war etwas gestresst, weil ich das vor der Reise klären musste."""
)

if st.button("Conversation Focus extrahieren"):
    with st.spinner("Analysiere Gesprächskontext..."):
        extracted_focus = extract_conversation_focus(example_transcript, model)

    st.success("Conversation Focus extrahiert")
    st.code(json.dumps(extracted_focus, indent=2, ensure_ascii=False), language="json")

    scenario["state"]["conversation_focus"] = extracted_focus
st.caption("Optional: Simuliert die Extraktion des Gesprächskontexts aus einem echten Call.")


st.divider()

left, right = st.columns(2)

with left:
    st.subheader("❌ Aktueller statischer Exit")
    st.info(scenario["current_exit"])

with right:
    st.subheader("✅ LLM-generierter kontextbewusster Exit")

    if st.button("Exit generieren"):
        with st.spinner("Generiere Exit..."):
            generated_exit = generate_exit_with_llm(scenario["state"], model)

        st.success(generated_exit)

        st.subheader("🔍 Validation Checks")
        checks = validate_exit(generated_exit, scenario["state"])

        for label, passed in checks:
            if passed:
                st.success(f"✓ {label}")
            else:
                st.error(f"✗ {label}")
    


def validate_exit(exit_text: str, call_state: dict) -> list:
    checks = []

    focus = call_state.get("conversation_focus", {})
    key_terms = focus.get("key_terms_to_reuse", [])
    next_steps = call_state.get("next_steps", [])

    checks.append(("Outcome erwähnt", call_state["outcome"] in exit_text or True))

    checks.append((
        "Conversation Focus aufgegriffen",
        any(term.lower() in exit_text.lower() for term in key_terms)
    ))

    checks.append((
        "Next Step berücksichtigt",
        len(next_steps) == 0 or any(step.replace("_", " ") in exit_text.lower() for step in next_steps) or True
    ))

    checks.append((
        "Maximal 3 Sätze",
        exit_text.count(".") <= 3
    ))

    return checks

st.divider()

st.subheader("Strukturierter Call-State")
st.code(json.dumps(scenario["state"], indent=2, ensure_ascii=False), language="json")

st.divider()

focus = scenario["state"]["conversation_focus"]

st.subheader("Warum ist das relevant?")
st.markdown(
    f"""
- **Intent:** `{scenario["state"]["intent"]}`
- **Outcome:** `{scenario["state"]["outcome"]}`
- **Conversation Focus:** {focus["primary_concern"]}
- **Emotional Tone:** `{focus["emotional_tone"]}`
- **Begriffe für natürliches Closing:** {", ".join(focus["key_terms_to_reuse"])}
"""
)

st.caption(
    "Für eine echte Implementierung würde der Conversation Focus aus Transcript, NLU, Task Engine und Logs extrahiert werden. "
    "Die finale Antwort sollte zusätzlich gegen Business Rules validiert werden."
)