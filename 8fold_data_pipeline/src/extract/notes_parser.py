import spacy
from spacy.matcher import Matcher
from typing import List
from src.models.observation import Observation

# Load the pre-trained NLP model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError(
        "Missing spaCy model. Run: python -m spacy download en_core_web_sm"
    )

def parse_recruiter_note(text: str) -> List[Observation]:
    """
    Extracts entities from unstructured text using a hybrid NLP pipeline.
    Leverages Named Entity Recognition (NER) and token matching.
    """
    # Pass the raw text through the NLP pipeline (tokenization, tagging, parsing, NER)
    doc = nlp(text)
    observations = []

    # 1. Token Attributes (Emails & Phones)
    # spaCy mathematically parses tokens under the hood, saving us from writing messy regex.
    emails = [token.text for token in doc if token.like_email]
    if emails:
        observations.append(Observation(
            field="emails", 
            value=emails, 
            source="note", 
            method="nlp_token_match"
        ))

    # We still use a strict regex pattern for E.164 phone validation downstream, 
    # but we can grab obvious numeric clusters here.
    import re
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phones = re.findall(phone_pattern, text)
    if phones:
        observations.append(Observation(
            field="phones", 
            value=phones, 
            source="note", 
            method="regex_heuristic"
        ))

    # 2. Named Entity Recognition (NER) for Locations
    # The model statistically predicts if a word is a Geopolitical Entity (GPE) or Location (LOC).
    locations = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
    if locations:
        # Take the most prominent recognized location
        observations.append(Observation(
            field="location",
            value={"city": locations[0], "state": None, "country": None},
            source="note",
            method="nlp_ner_extraction"
        ))

    # 3. Rule-Based NLP Matcher for Skills
    # Unlike naive string matching, this understands tokens. It can catch 
    # "Machine Learning" even if there is an extra space or strange punctuation.
    matcher = Matcher(nlp.vocab)
    
    # Define our target linguistic patterns
    patterns = [
        [{"LOWER": "python"}],
        [{"LOWER": "java"}],
        [{"LOWER": "react"}],
        [{"LOWER": "aws"}],
        [{"LOWER": "machine"}, {"LOWER": "learning"}],
        [{"LOWER": "random"}, {"LOWER": "forest"}],
        [{"LOWER": "xgboost"}]
    ]
    matcher.add("TECH_SKILLS", patterns)
    
    matches = matcher(doc)
    
    # Deduplicate and title-case the extracted skill tokens
    skills = list(set([doc[start:end].text.title() for match_id, start, end in matches]))
    
    for skill in skills:
        observations.append(Observation(
            field="skills",
            value=[skill],
            source="note",
            method="nlp_matcher"
        ))

    return observations