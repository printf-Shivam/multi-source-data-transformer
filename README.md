# Eightfold Multi-Source Candidate Data Transformer

A deterministic, explainable ETL pipeline that ingests candidate data from ATS JSON, GitHub API, and Recruiter Notes (via spaCy NLP), then merges them into a single trusted canonical profile using a Source Authority Matrix and runtime-configurable projection.

---

## Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

## Exact Run Steps

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

### Quiet mode (only JSON output)

```bash
python main.py --ats data/sample_ats.json --config config.json --quiet
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

```bash
pytest -v
```

All tests pass.

---

## Demo Video

**Demo Video Link (≈2 minutes)**
  (please use earphones/headphones the audio is extremely low, tried my best with available gears)
  
  https://drive.google.com/file/d/1HjqibxtbDwr5NgiLUmzFtY830mT0U64b/view?usp=sharing


The video demonstrates:

- End-to-end run with all three sources
- Default output and custom config output
- design decision (Source Authority Matrix, Observation pattern)
- One edge case (invalid phone → note fills the gap)


---

## Architecture (5-Stage Pipeline)

| Stage | Responsibility |
|-------|----------------|
| Extract | Isolated ingestion from ATS (JSON), GitHub (API), and Recruiter Notes (spaCy NLP + regex). Degrades gracefully on errors. |
| Normalize | Dates → YYYY-MM; Phones → validated E.164 (invalid → null); Skills → canonical (e.g., `react.js` → `React`); Country → ISO-3166. |
| Entity Link | Verifies GitHub identity via exact email or ATS `github_url`. Unlinked GitHub data is dropped ("missing > wrong"). |
| Merge | Column-level conflict resolution using a Source Authority Matrix. Confidence = winner’s weight, or 1.0 if sources agree (consensus boost). |
| Load (Project) | Applies runtime JSON config to select, rename, normalize, and validate final output. |

---

## Source Authority Matrix (Weights)

| Category | ATS | GitHub | Recruiter Note |
|----------|-----|--------|----------------|
| Identity (Name, Email) | 0.9 | 0.4 | 0.5 |
| Technical Skills | 0.6 | 0.9 | 0.5 |
| Education | 0.9 | 0.0 (Zero-Trust) | 0.0 |
| Experience | 0.85 | 0.3 | 0.0 |
| Location | 0.85 | 0.3 | 0.6 |

**Consensus Boost:** If multiple sources agree, confidence → **1.0**

`overall_confidence = mean(all field confidences)`

---

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| candidate_id | string | Candidate identifier |
| full_name | string | Candidate's full name |
| primary_email | string | Primary email address |
| phone | string | E.164 formatted phone number |
| top_skill | string | Highest confidence skill |
| years_experience | number | Total years of experience |
| location | object | City, region, country |
| all_skills | string[] | All merged skills |
| all_emails | string[] | All emails from all sources |
| all_phones | string[] | All valid phones |
| overall_confidence | number | Mean of all field confidences |
| provenance | array | Source and method for each field |

---

## Assumptions & Descoped Items

### Assumptions

- GitHub API is used as the unstructured source (unauthenticated, 60 req/hr limit)
- Recruiter notes are plain `.txt` files with free-text
- ATS JSON structure is configurable via `ats_mapping.json`
- Pipeline processes one candidate at a time (batch mode)

### Deliberately Descoped

- **UI / Frontend Polish** → CLI only; backend correctness prioritized  
- **Probabilistic Imputation** → No ML or generative AI; missing fields stay null  
- **PDF / DOCX Resume Parsing** → Descoped in favor of structured JSON + REST APIs  
- **Persistent Storage Layer** → Stateless and batch-oriented  
- **Real-time Streaming** → Designed for batch runs  

---


## Built With

- **Pydantic** → Runtime type validation  
- **spaCy** → NLP for recruiter notes (extractive NER)  
- **phonenumbers** → E.164 validation  
- **python-dateutil** → Date parsing  
- **requests** → GitHub API calls  