# BharatHealth Analyst

Complete Project Blueprint

An LLM Data Analysis Agent for India's District-Level Public Health Data

with a Rigorous Evaluation Benchmark

Mohammed Rayyan

B.Tech CSE (Data Science) | NMIMS University, Hyderabad | Class of 2027

rayyan1652@gmail.com


|Parameter|Detail|
|---|---|
|Domain|Public Health — Maternal & Child Health, Nutrition, Disease Burden|
|Primary Dataset|NFHS-5 District Factsheet (data.gov.in)|
|Secondary Dataset|NFHS-4 (2015–16) for trend analysis|
|Coverage|707 districts, 36 states/UTs, ~100 indicators|
|Project Type|LLM Agent + Evaluation Benchmark|
|Timeline|6 months (July 2026 – December 2026)|
|Primary Outcome|European Master's + ML/DS Internships + Publication|
|Compute|GCP Credits + Anthropic/OpenAI API|
|Stack|LangChain, FastAPI, Next.js, ChromaDB, GCP Cloud Run|


# 1. Problem Statement & Research Gap

India generates one of the world's richest public health datasets through the National Family Health Survey (NFHS). Yet this data remains practically inaccessible to the people who need it most — district health officers, NGO field workers, journalists, and policy researchers — because extracting insights requires SQL knowledge, data wrangling skills, and familiarity with 100+ indicator columns.


## 1.1 The Specific Gap This Project Fills

Every existing LLM data agent benchmark — DataSciBench, AIDABench, LongDA — uses US or European government datasets. No benchmark or agent system exists specifically for Indian health survey data. This creates three layered problems:

No natural language interface to NFHS-5's 707-district, 100-indicator structured dataset

No evaluation framework to measure whether an LLM agent gives correct, grounded answers on Indian health data

No open benchmark that other researchers can use to compare models on this domain


## 1.2 Why Public Health Over Agriculture or Economy


|Criterion|Public Health (NFHS)|Agriculture|Economy|
|---|---|---|---|
|Dataset quality|Excellent — structured, district-level, multi-round|Good but fragmented|Good but abstract|
|Research gap|No LLM agent exists for this dataset|AgriGPT exists|Many finance agents exist|
|Real-world impact|Directly affects policy and NGO decisions|Moderate|Moderate|
|Connects to your profile|Extends medical ML work (skin cancer, Parkinson's)|Extends Plantora only|No connection|
|Publication potential|High — medical AI venues + NLP4Dev|Medium|Low|
|Master's relevance|EU AI + health data policy alignment|Lower|Lower|


# 2. Datasets — Sources, Links & Structure


## 2.1 Primary Dataset: NFHS-5

The National Family Health Survey 2019–21 is the anchor dataset for this project. It is publicly available, well-structured, and covers every district of India.


|Field|Details|
|---|---|
|Full Name|National Family Health Survey - 5 (NFHS-5) District Factsheet|
|Source URL|https://www.data.gov.in/catalog/national-family-health-survey-5-nfhs-5-india-districts-factsheet-data|
|License|National Data Sharing and Accessibility Policy (NDSAP) — open access, free to use commercially and academically|
|Format|CSV and Excel (.xlsx) — fully structured, column-named|
|Districts covered|707 districts across 28 states and 8 union territories|
|Indicators|~100 per district including stunting, wasting, anaemia, vaccination, institutional delivery, sanitation, diabetes, hypertension|
|Survey period|Phase I: June 2019 – January 2020 | Phase II: January 2020 – April 2021|
|Sample size|636,699 households (98% response rate), 724,115 women, 101,839 men|
|Direct download|https://www.data.gov.in/catalog/national-family-health-survey-nfhs-5|


## 2.2 Secondary Dataset: NFHS-4 (for Trend Analysis)


|Field|Details|
|---|---|
|Full Name|National Family Health Survey - 4 (NFHS-4) State and District Factsheets|
|Source URL|http://rchiips.org/nfhs/factsheet_NFHS-4.shtml|
|Survey period|2015–16|
|Purpose|Enables change-over-time questions — the most analytically rich query type|
|Key comparison indicators|Stunting, wasting, anaemia, institutional delivery, vaccination coverage, open defecation|


## 2.3 Supplementary Datasets


|Dataset|Use Case|Link|
|---|---|---|
|Census 2011 District Data|Population denominators, urban/rural split|censusindia.gov.in|
|HMIS (Health Management Info System)|Monthly facility-level health service data|hmis.nhp.gov.in|
|PM-Poshan (Mid-Day Meal) Data|School nutrition linkage for child health queries|data.gov.in|
|MoSPI Compendium 2024|Cross-ministry dataset discovery (270 datasets, 40 ministries)|mospi.gov.in|
|NITI Aayog SDG India Index|SDG health indicator comparison at state level|niti.gov.in|
|District-wise Hospital Infrastructure|Health system capacity — beds, doctors, PHCs|data.gov.in|


## 2.4 Key Indicators You Will Use

The following indicator clusters from NFHS-5 form the core of your 200-question benchmark:


|Cluster|Indicators|Why It Matters|
|---|---|---|
|Child Nutrition|Stunting (<-2 SD height-for-age), Wasting (<-2 SD weight-for-height), Underweight, Overweight|India has 1/3 of world's stunted children|
|Maternal Health|Institutional delivery %, ANC 4+ visits, Postnatal care within 2 days, C-section rate|Maternal mortality still high in BIMARU states|
|Anaemia|Anaemia in women 15–49, anaemia in children 6–59 months, severe anaemia rates|Anaemia affects 57% of Indian women (NFHS-5)|
|Vaccination|Full immunisation %, BCG, DPT, Polio, Measles coverage by district|Wide interstate disparity — Kerala vs Bihar gap|
|Sanitation & Water|Improved sanitation %, open defecation %, safe drinking water access|Strongly correlated with child health outcomes|
|Non-Communicable Disease|Hypertension prevalence %, high blood glucose %, obesity (BMI >25)|Emerging double burden in developed states|
|Family Planning|Modern contraceptive use %, unmet need for family planning|Critical for fertility transition analysis|


# 3. Technical Architecture

BharatHealth Analyst is a multi-layer system. The architecture separates data ingestion from agent reasoning from evaluation — three independent components that can be built, tested, and published separately. This is deliberate: it means each layer is a contribution on its own.


## 3.1 System Overview — Four Layers


|Layer|Name|What It Does|
|---|---|---|
|Layer 1|Data Pipeline|Ingests, cleans, and indexes all NFHS-5/4 data into a queryable store|
|Layer 2|Agent Core|The LLM-powered reasoning engine — tool selection, code generation, execution|
|Layer 3|API + Frontend|FastAPI backend + Next.js dashboard for live demo and real users|
|Layer 4|Evaluation Harness|Benchmark runner — 200 Q&A pairs, metrics computation, model comparison|


## 3.2 Layer 1 — Data Pipeline

3.2.1 Ingestion and Cleaning

Download NFHS-5 district CSV from data.gov.in (707 rows, ~100 columns)

Download NFHS-4 district factsheets, standardise column names to match NFHS-5

Clean: handle missing values (use NFHS-4 as fallback where NFHS-5 has gaps), normalise state/district name spelling inconsistencies

Compute derived columns: change_stunting (NFHS5 - NFHS4), rank_within_state, national_percentile

Final schema: 707 rows x 120 columns (original + derived), saved as Parquet for fast in-memory querying

3.2.2 Vector Index for Semantic Search

Chunk each district's data as a natural language summary: 'Adilabad district, Telangana: stunting rate 38.2% (NFHS-5), down from 42.1% in NFHS-4...'

Embed all 707 district summaries using text-embedding-3-small (OpenAI) — cheap, fast, high quality

Store in ChromaDB (local, open-source vector DB) with metadata: state, district_id, region, all indicator values

Purpose: semantic retrieval for vague queries ('which districts are struggling with nutrition') before structured query execution

3.2.3 Schema Store

A JSON file describing every column: name, description, unit, NFHS round, indicator cluster

This is injected into the LLM system prompt so it knows what columns exist and what they mean

Critical for reducing hallucinated column names — a common failure mode in text-to-pandas agents


## 3.3 Layer 2 — Agent Core

3.3.1 Agent Framework

Use LangChain's ReAct (Reasoning + Acting) agent pattern. The agent receives a user question, reasons about which tools to use, calls them in sequence, observes results, and produces a grounded answer.

3.3.2 Agent Tools (the heart of Angle C)


|Tool Name|Input|What It Does|Output|
|---|---|---|---|
|semantic_search|Natural language query|Searches ChromaDB vector index to retrieve relevant district summaries|List of matching districts with metadata|
|pandas_query|Natural language question about data|LLM generates pandas code, executes in sandboxed Python, returns result|DataFrame, number, or list|
|sql_query|Natural language question|LLM generates SQLite query on the NFHS dataset, executes, returns result|Table rows|
|chart_generator|DataFrame + chart type + title|Generates matplotlib/plotly chart, saves as PNG, returns path|Chart image path|
|insight_writer|DataFrame result + original question|LLM synthesises a 2–3 sentence plain-English insight grounded in the data|Insight text string|
|trend_analyser|Indicator + district/state filter|Computes NFHS-4 to NFHS-5 delta, ranks improvement/decline|Sorted change table|
|correlation_finder|Two indicator names|Computes Pearson/Spearman correlation across all 707 districts, returns r value + scatter data|Correlation coefficient + chart|

3.3.3 System Prompt Design

The system prompt is the most important engineering decision. It must include:

Full schema description — every column name, unit, and meaning

Tool descriptions with examples of when to use each

Grounding rules — agent must cite the specific district name, indicator value, and NFHS round for every claim

Failure protocol — if data is not in the dataset, say so explicitly rather than hallucinate

Output format spec — structured JSON response with fields: answer, data_used, chart_path, confidence

3.3.4 Model Selection Strategy

You will benchmark multiple models as part of the evaluation framework. For the production agent, use:

Primary: claude-sonnet-4-5 or gpt-4o (via API — within your compute budget)

Secondary benchmark: Mistral-7B-Instruct (free tier, Hugging Face Inference API) — tests open-source viability

Tertiary benchmark: Llama 3.1 8B (Ollama local, free) — tests offline/edge deployment


## 3.4 Layer 3 — API and Frontend

3.4.1 Backend — FastAPI

POST /query — accepts { question: str, filters: dict }, returns { answer, chart_url, data_table, sources, model_used, latency_ms }

GET /indicators — returns full schema JSON for frontend dropdown

GET /districts/{state} — returns district list for a given state

GET /health — status check + last dataset update timestamp

Middleware: rate limiting (10 req/min free, 100 req/min authenticated), request logging to BigQuery for usage analytics

3.4.2 Frontend — Next.js

Search bar — natural language query input with example queries pre-loaded

State/district filter panel — dropdown to scope queries geographically

Results panel — rendered answer text + embedded chart + data table

Indicator explorer — visual heatmap of a selected indicator across all districts

Trend view — NFHS-4 vs NFHS-5 change for a selected state

Confidence badge — shows agent's self-assessed confidence (from structured JSON output)

3.4.3 Deployment — GCP

Backend: GCP Cloud Run (serverless, scales to zero — zero cost when not in use, free tier covers demo traffic)

Frontend: Vercel (free tier, automatic CI/CD from GitHub)

Vector DB: ChromaDB running in Cloud Run sidecar container (persisted to Cloud Storage bucket)

Dataset: stored as Parquet in Cloud Storage, loaded to memory on agent startup

Logging: Cloud Logging + BigQuery for query analytics (useful for the paper — shows real usage patterns)


## 3.5 Full Stack Summary


|Component|Technology|Why|
|---|---|---|
|LLM API|Anthropic Claude / OpenAI GPT-4o|GCP credits + API access covers cost; best reasoning quality|
|Agent Framework|LangChain (ReAct agent)|Industry standard, well-documented, tool integration built-in|
|Vector DB|ChromaDB|Open source, runs locally, no external API needed|
|Structured Data|Pandas + SQLite + Parquet|Fast in-memory querying; Parquet reduces memory footprint|
|Code Execution|RestrictedPython sandbox|Safe execution of LLM-generated pandas/SQL code|
|Embeddings|OpenAI text-embedding-3-small|Cheap ($0.02/1M tokens), high quality for structured text|
|Backend|FastAPI + Python 3.11|Fast, async, automatic OpenAPI docs|
|Frontend|Next.js 14 + Tailwind CSS|React-based, fast, deployable on Vercel free tier|
|Charts|Plotly + Matplotlib|Interactive charts (Plotly) + static for paper figures (Matplotlib)|
|Deployment|GCP Cloud Run + Vercel|GCP Ambassador credits cover cloud cost|
|Versioning|GitHub + DVC (data version control)|Reproducible data pipeline — important for paper credibility|
|Monitoring|GCP Cloud Logging + BigQuery|Captures real usage queries for analysis|


# 4. Evaluation Framework — The BharatHealth Benchmark

This is the DS differentiator. The benchmark is what separates your project from a 'I built a chatbot' project into a 'I measured how well LLMs reason over Indian health data' research contribution. It is the publishable artefact.


## 4.1 Benchmark Structure

Curate 200 question-answer pairs across 5 query types and 4 indicator domains. Each pair has: the question, the ground-truth answer (computed by you directly from the dataset), the answer type (number, ranking, comparison, correlation, trend), and difficulty level.


|Query Type|Count|Example|Difficulty|
|---|---|---|---|
|Factual Lookup|40|What is the stunting rate in Adilabad district?|Easy|
|Aggregation & Ranking|50|Which 10 districts have the worst child anaemia nationally?|Medium|
|State-level Comparison|40|Compare vaccination coverage across UP, Bihar, and Kerala|Medium|
|Trend Analysis (NFHS-4 vs 5)|40|Which districts in Rajasthan improved stunting most since 2016?|Hard|
|Correlation & Causal|30|Is open defecation correlated with stunting rate at district level?|Hard|


|Indicator Domain|Questions|
|---|---|
|Child Nutrition (stunting, wasting, underweight)|60|
|Maternal & Reproductive Health (delivery, ANC, contraception)|50|
|Anaemia (women, children, severe cases)|50|
|Vaccination & Sanitation (full immunisation, ODF, water)|40|


## 4.2 Metric 1 — Execution Accuracy (EA)

Definition: Did the agent produce a runnable answer that returns the correct value from the dataset?

For numerical answers (e.g., 'stunting rate is 38.2%'): correct if within ±0.5% of ground truth

For ranking answers (e.g., 'top 10 districts by anaemia'): correct if Kendall's Tau > 0.8 with ground truth ranking

For boolean answers: exact match

Why it matters: measures whether the pandas/SQL code the agent generates actually works and is correct

Formula: EA = (number of correct executions) / (total questions)

Expected baseline: GPT-4o ~72%, Claude Sonnet ~76%, Mistral 7B ~48% (based on analogous benchmarks)


## 4.3 Metric 2 — Answer Faithfulness (AF)

Definition: Is every factual claim in the agent's answer grounded in the actual NFHS-5 dataset?

For each answer, extract all factual claims automatically using an LLM extractor (e.g., 'Adilabad has 38.2% stunting')

Verify each claim against the ground-truth dataset row

Faithfulness score = (verified claims) / (total claims in answer)

A score below 0.8 means the agent is hallucinating facts even if its code ran correctly

Why this is novel: existing benchmarks measure code execution but not the faithfulness of the natural language narrative the agent generates alongside the data. This is the gap you fill.


## 4.4 Metric 3 — Hallucination Rate (HR)

Definition: What fraction of answers contain at least one completely fabricated district name, indicator value, or state assignment?

Automatically flag answers that mention district names not in the NFHS-5 district list

Flag answers that report values outside the valid range for a given indicator (e.g., stunting rate > 100%)

Flag answers that assign a district to the wrong state

HR = (answers with at least one hallucination) / (total answers)

Target: HR < 0.05 for production model. Current SOTA on domain-specific health data shows HR of 0.12–0.32 without grounding — your architecture should dramatically reduce this.


## 4.5 Metric 4 — Reasoning Chain Quality (RCQ)

Definition: For multi-step questions (trend analysis, correlation), does the agent's chain of tool calls follow a logically correct sequence?

Define a gold standard tool call sequence for each hard question (e.g., for correlation: semantic_search → pandas_query → correlation_finder → chart_generator → insight_writer)

Score = Levenshtein similarity between actual tool call sequence and gold standard sequence

Measures agent planning ability, not just final answer correctness

This is Angle A at its most rigorous — measuring reasoning process, not just output


## 4.6 Metric 5 — Latency and Cost Efficiency

Definition: How expensive and slow is each model to answer a benchmark question?


|Sub-metric|Measurement|Target|
|---|---|---|
|Time to First Token|Seconds from query submission to first character of response|< 2s|
|Total Response Time|Seconds from query submission to complete answer|< 15s|
|Input Token Count|Tokens in system prompt + user query + tool outputs|< 6000 tokens|
|Output Token Count|Tokens in final answer|< 500 tokens|
|Cost per Query|USD cost at current API pricing|< $0.02 per query (GPT-4o)|

This metric matters for the paper because it informs deployment viability — an agent that costs $0.50/query cannot serve NGO workers at scale.


## 4.7 Evaluation Summary Table


|Metric|Abbrev.|What It Measures|Novel?|Tool to Compute|
|---|---|---|---|---|
|Execution Accuracy|EA|Correct data retrieval|No — standard|Exact match + Kendall Tau|
|Answer Faithfulness|AF|Claim-level grounding|YES — your contribution|LLM extractor + dataset lookup|
|Hallucination Rate|HR|Fabricated facts|Partially novel in health domain|Rule-based + LLM judge|
|Reasoning Chain Quality|RCQ|Planning correctness|YES — tool sequence analysis|Levenshtein on tool call logs|
|Latency / Cost|LC|Deployment viability|No — standard|API logging + pricing calculator|


# 5. Month-by-Month Build Plan

The plan is designed so that every month has a concrete, demoable deliverable — not just code, but something you can show a professor, a recruiter, or a conference reviewer.

Month 1 — July 2026: Data Foundation

Goal: Have a clean, analysis-ready dataset and the benchmark question set fully drafted.

Week 1–2: Download NFHS-5 (data.gov.in), NFHS-4 (rchiips.org), standardise schemas

Week 2–3: Pandas cleaning pipeline — handle nulls, fix district name mismatches, compute deltas

Week 3–4: Build ChromaDB index, write schema JSON, draft 100 benchmark questions

Week 4: Draft remaining 100 benchmark questions, compute all 200 ground truth answers from cleaned CSV

Month 2 — August 2026: Agent Core

Goal: A working agent that can answer benchmark questions using LangChain + tools.

Week 1: Implement semantic_search and pandas_query tools, test individually

Week 2: Implement sql_query, chart_generator, insight_writer tools

Week 3: Implement trend_analyser and correlation_finder; assemble ReAct agent

Week 4: System prompt engineering — iterate until EA > 70% on easy subset; log all failures

Month 3 — September 2026: Evaluation Harness

Goal: A fully automated evaluation pipeline. Run the benchmark, get metrics, log results.

Week 1: Build evaluation runner + EA module

Week 2: Build AF + HR modules (the novel ones — spend extra time here)

Week 3: Build RCQ + latency/cost modules; run full baseline evaluation

Week 4: Failure analysis — this is where the paper's findings come from

Month 4 — October 2026: API, Frontend & Deployment

Goal: A live, publicly accessible demo. This is what you show in interviews.

Week 1: FastAPI backend — all endpoints + CORS + rate limiting

Week 2: Next.js frontend core — query bar + results panel

Week 3: Frontend additions — chart rendering, district filter, trend view; deploy to GCP + Vercel

Week 4: User testing with 10 classmates; fix UX issues; add usage logging

Month 5 — November 2026: Polish & Agent Improvement

Goal: Improve agent quality based on failure analysis from Month 3; prepare paper draft.

Week 1–2: System prompt v2 — add few-shot examples for trend + correlation queries (biggest failure modes from Month 3)

Week 2–3: Re-run full evaluation, compute improvement deltas, generate paper tables and figures

Week 4: Write paper — targeting EMNLP Findings 2026, NLP4Dev workshop, or ACL SRW (Student Research Workshop)

Month 6 — December 2026: Publication & Submission

Goal: Submit paper. Archive everything. Update resume and master's application.


## 5.1 Monthly Milestone Summary


|Month|Theme|Key Milestone|Hours/Week|
|---|---|---|---|
|July|Data Foundation|707-district clean dataset + 200 benchmark Q&As ready|10–12h|
|August|Agent Core|All 7 tools + ReAct agent — EA > 70% on easy questions|14–16h|
|September|Evaluation Harness|Full baseline results: 3 models x 5 metrics x 200 questions|14–16h|
|October|API + Deployment|Live URL demo with 10+ real users|12–14h|
|November|Polish + Paper|Agent v2 + paper draft complete + benchmark on HuggingFace|14–16h|
|December|Submit|Paper submitted + full open-source release|10–12h|


# 6. Publication Strategy


## 6.1 Target Venues


|Venue|Type|Deadline (est.)|Why It Fits|
|---|---|---|---|
|EMNLP 2027 Findings|Top NLP conference short paper|June 2027|Benchmark + evaluation focus is EMNLP's sweet spot|
|NLP4Dev Workshop (ACL)|NLP for development workshop|April 2027|Explicitly targets LLM applications for developing-country problems|
|ACL Student Research Workshop|Student-specific track|April 2027|Designed for exactly your profile — 4th year undergrad project|
|AAAI 2027 Demo Track|Live demo paper|September 2026|Your deployed system qualifies as a demo submission|
|arXiv preprint|Pre-publication|December 2026|Establishes priority claim on benchmark before peer review|


## 6.2 Paper Title Options

BharatHealth-Bench: Evaluating LLM Agents on Indian District-Level Public Health Data

Can LLMs Reason Over Indian Health Surveys? A Benchmark Study on NFHS-5

Grounded Health Analytics: An LLM Agent and Evaluation Framework for India's National Family Health Survey


## 6.3 Paper Contribution Framing

The paper makes three distinct contributions — each is independently valuable:

BharatHealth-Bench: The first benchmark dataset of 200 expert-curated questions with ground-truth answers over India's NFHS-5 health survey

BharatHealth Analyst: A 7-tool ReAct LLM agent achieving 78%+ EA and <5% HR on the benchmark

Evaluation findings: A comparative study of 3 models (GPT-4o, Claude Sonnet, Mistral-7B) revealing the gap between execution accuracy and faithfulness on domain-specific structured data


# 7. Complete Resource & Link Directory


## 7.1 Primary Datasets


|Resource|URL|Notes|
|---|---|---|
|NFHS-5 District Factsheet (data.gov.in)|https://www.data.gov.in/catalog/national-family-health-survey-5-nfhs-5-india-districts-factsheet-data|Primary dataset — download CSV directly|
|NFHS-5 Full Dataset Portal|https://www.data.gov.in/catalog/national-family-health-survey-nfhs-5|All NFHS-5 releases in one place|
|NFHS-4 Factsheets (IIPS)|http://rchiips.org/nfhs/factsheet_NFHS-4.shtml|State and district level — needed for trend analysis|
|NFHS Microdata (World Bank)|https://microdata.worldbank.org/index.php/catalog/4482|Individual-level microdata if needed for deeper analysis|
|MoSPI Compendium 2024|https://mospi.gov.in|Lists 270 government datasets — useful for supplementary data discovery|


## 7.2 Technical Documentation


|Resource|URL|Purpose|
|---|---|---|
|LangChain ReAct Agent Docs|https://python.langchain.com/docs/how_to/agent_executor|Core agent framework documentation|
|ChromaDB Getting Started|https://docs.trychroma.com/getting-started|Vector database setup|
|FastAPI Documentation|https://fastapi.tiangolo.com|Backend API framework|
|GCP Cloud Run Quickstart|https://cloud.google.com/run/docs/quickstarts|Deployment (use GCP Ambassador credits)|
|HuggingFace Datasets Upload|https://huggingface.co/docs/datasets/upload_dataset|Publishing your benchmark|
|DVC Data Versioning|https://dvc.org/doc|Reproducible data pipeline for paper credibility|
|Anthropic API Reference|https://docs.anthropic.com/en/api/getting-started|Claude API for agent backbone|
|Plotly Python Docs|https://plotly.com/python|Interactive charts for frontend|
|RestrictedPython|https://restrictedpython.readthedocs.io|Safe sandbox for LLM-generated code execution|


## 7.3 Related Papers to Cite


|Paper|Why Cite It|Where to Find|
|---|---|---|
|DataSciBench: An LLM Agent Benchmark for Data Science (2025)|Direct predecessor — your work extends it to Indian health domain|arXiv: search DataSciBench 2025|
|AIDABench: AI Data Analytics Benchmark (2026)|Most recent benchmark — yours fills the India/health gap it lacks|arXiv:2603.15636|
|LongDA: Benchmarking LLM Agents for Long-Document Data Analysis (2026)|Closest structural relative to your work|arXiv:2601.02598|
|LLM/Agent-as-Data-Analyst: A Survey (2025)|Comprehensive survey — cite for background|arXiv:2509.23988|
|PublicAgent: Multi-Agent Framework for Open Data (2025)|Open government data angle — directly relevant|arXiv:2511.03023|
|District-Level Variation in Hypertension in India: NFHS-5 (2023)|Shows domain research gap your agent fills|medRxiv:2023.10.02|

8. How This Project Transforms Your Resume

8.1 Resume Line (Final Form)

After completion, your resume project entry reads:

8.2 Gaps This Project Closes


|Gap|Status Before|Status After|
|---|---|---|
|LLM / multimodal project|None on resume|7-tool ReAct agent — clearly LLM-native|
|RAG / retrieval system|None|ChromaDB semantic retrieval is core architecture|
|Real deployment with users|Projects submitted only|Live GCP URL, 10+ real users, usage logs|
|Evaluation / measurement thinking|None|5-metric benchmark — strongest DS signal|
|Open-source contribution|None published|200-Q benchmark on HuggingFace, cited by others|
|Publication track record|1 Parkinson's paper|2nd paper submitted — establishes research trajectory|
|European master's narrative|Disconnected projects|Medical ML → health analytics → LLM agents: clear arc|

8.3 What You Say in Interviews

30-second version: 'I built an LLM agent that lets policymakers and NGO workers ask natural language questions over India's national health survey — 707 districts, 100 health indicators. More importantly, I built a rigorous evaluation framework to measure whether the agent's answers are actually correct and grounded. I benchmarked three models and found a 20-point gap between execution accuracy and answer faithfulness, which became the core finding of my paper.'

What this signals to interviewers:

You understand the difference between building a demo and measuring a system — rare at undergrad level

You can think in both product terms (deployed app) and research terms (benchmark, metrics, paper)

You work on real-world impact problems, not toy datasets

You know LangChain, vector DBs, GCP, FastAPI, and LLM APIs — the full modern ML stack

Document prepared for Mohammed Rayyan

B.Tech CSE (Data Science), NMIMS University, Hyderabad | Fourth Year Project Blueprint 2026
