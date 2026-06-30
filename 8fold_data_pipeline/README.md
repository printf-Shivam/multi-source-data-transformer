# Eightfold Multi-Source Candidate Data Transformer

## Installation
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run with all sources (ATS + GitHub + Recruiter Note)
python main.py --ats data/sample_ats.json --note data/recruiter_note.txt --config config.json

# Run with ATS only (auto-derives GitHub from ATS URL)
python main.py --ats data/sample_ats.json --config config.json

# Run with explicit GitHub (overrides auto-derivation)
python main.py --ats data/sample_ats.json --github johndoe99 --config config.json

# Offline run (skip GitHub API)
python main.py --ats data/sample_ats.json --config config.json --no-github

# Save output to file
python main.py --ats data/sample_ats.json --config config.json --output result.json

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

pytest -v

