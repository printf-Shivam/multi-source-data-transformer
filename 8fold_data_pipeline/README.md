# Eightfold Multi-Source Candidate Data Transformer

A candidate profile transformation system that merges structured and unstructured data from multiple sources such as ATS records, GitHub profiles, and recruiter notes into a unified normalized candidate profile.

---

## Features

- Multi-source candidate data ingestion:
  - ATS JSON
  - GitHub profile
  - Recruiter notes
- Entity normalization and conflict resolution
- Confidence scoring for merged data
- Provenance tracking for every field
- Optional offline mode (skip GitHub API)

---

## Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

## Usage

### Run with all sources (ATS + GitHub + Recruiter Note)

```bash
python main.py --ats data/sample_ats.json --note data/recruiter_note.txt --config config.json
```

### Run with ATS only (auto-derives GitHub from ATS URL)

```bash
python main.py --ats data/sample_ats.json --config config.json
```

### Run with explicit GitHub (overrides auto-derivation)

```bash
python main.py --ats data/sample_ats.json --github johndoe99 --config config.json
```

### Offline run (skip GitHub API)

```bash
python main.py --ats data/sample_ats.json --config config.json --no-github
```

### Save output to file

```bash
python main.py --ats data/sample_ats.json --config config.json --output result.json
```

---

## Sample Output

```json
{
  "candidate_id": "CAND-8892",
  "full_name": "John Michael Doe",
  "primary_email": "john.doe@email.com",
  "phone": "+14155550199",
  "top_skill": "JavaScript",
  "years_experience": 6.4,
  "location": {
    "city": "San Francisco",
    "region": "CA",
    "country": "US"
  },
  "all_skills": [
    "JavaScript",
    "React",
    "Python",
    "AWS",
    "PostgreSQL",
    "C"
  ],
  "all_emails": [
    "john.doe@email.com",
    "johndoe@gmail.com",
    "johndoe.tech@email.com"
  ],
  "all_phones": [
    "+14155550199"
  ],
  "overall_confidence": 0.81,
  "provenance": [
    {
      "field": "candidate_id",
      "source": "ats",
      "method": "merge"
    },
    {
      "field": "full_name",
      "source": "ats",
      "method": "merge"
    },
    {
      "field": "headline",
      "source": "ats",
      "method": "merge"
    },
    {
      "field": "location",
      "source": "ats",
      "method": "merge"
    }
  ]
}
```

---

## Testing

Run test suite using:

```bash
pytest -v
```

---

## Processing Pipeline

The transformation flow follows these stages:

1. Extract  
2. Normalize  
3. Entity Link  
4. Conflict Resolution  
5. Confidence Scoring  
6. Projection  
7. Validation  

---

## Output Schema

### Core Fields

- `candidate_id`
- `full_name`
- `primary_email`
- `phone`
- `top_skill`
- `years_experience`

### Location Object

```json
{
  "city": "string",
  "region": "string",
  "country": "string"
}
```

### Aggregated Fields

- `all_skills`
- `all_emails`
- `all_phones`

### Metadata

- `overall_confidence`
- `provenance`