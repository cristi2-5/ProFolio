# Auto-Apply: Job Hunter & Interview Strategist

## Descrierea Aplicației

Auto-Apply este o platformă inteligentă creată pentru a automatiza și eficientiza procesul de căutare a unui loc de muncă sau internship. Construită pentru a combate "oboseala aplicantului", aplicația folosește o arhitectură bazată pe agenți AI pentru a prelua sarcinile repetitive și consumatoare de timp.

Sistemul permite utilizatorilor să își încarce CV-ul de bază și să definească rolul dorit. Din acel moment, patru agenți autonomi preiau controlul:

- **CV Profiler**: Parsează automat CV-ul încărcat și extrage structurat datele esențiale ale candidatului (abilități, experiență, educație, tehnologii), eliminând nevoia oricărei introduceri manuale de date.
- **Job Scanner**: Caută zilnic pe platformele de recrutare și aduce cele mai relevante oportunități direct într-un panou centralizat.
- **CV Optimizer**: Analizează descrierea fiecărui job (JD) și reformulează dinamic CV-ul și Scrisoarea de Intenție pentru a trece de filtrele ATS (Applicant Tracking System), păstrând strictețea datelor reale ale candidatului.
- **Interview Coach**: Generează materiale de pregătire personalizate (întrebări tehnice, comportamentale și fișe de recapitulare) bazate exact pe tehnologiile cerute de angajator.
- **Job Scanner Engine**: Sistemul de descoperire automată a joburilor care utilizează API-uri externe (Adzuna) și algoritmi de deduplicare avansați pentru a menține un dashboard curat și relevant.

În plus, aplicația oferă un sistem de evaluare comparativă (Competitive Benchmarking) pentru a arăta candidaților unde se situează față de cerințele pieței și ce abilități trebuie să mai dezvolte.

---

## 🚀 Run Locally with Docker Compose

The fastest way to spin up the full stack (Postgres + FastAPI backend + React/Vite frontend) on your machine.

### Prerequisites

- **Docker Desktop** installed and running ([download](https://www.docker.com/products/docker-desktop/)).
- A **Gemini API key** — the backend talks to Google's Gemini via an OpenAI-compatible endpoint. Generate one at https://aistudio.google.com/app/apikey.
- An **Adzuna app id + key** — used by the Job Scanner agent. Register a free developer account at https://developer.adzuna.com/ (free tier: 250 requests/month).

### Setup

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY (your Gemini key — env-var name kept for back-compat),
# ADZUNA_APP_ID, ADZUNA_APP_KEY. Leave the rest at defaults for local dev.
docker compose up --build
```

### Access

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs

### First-time use

1. Open the frontend and **register an account**.
2. **Upload your CV** (PDF or DOCX) — the CV Profiler agent parses it automatically.
3. **Set your job preferences** (title, location, keywords, seniority).
4. Click **"Scan jobs"** to fetch matching opportunities from Adzuna.

### Common pitfalls

- **Port already in use** (5432, 8000, or 5173): another project is bound to that port. `docker compose down` other projects, or change the host-side port in `docker-compose.yml`.
- **First build is slow** (3–5 minutes): the Python image installs all backend deps, and the frontend image runs `npm install`. Subsequent builds are cached.
- **Postgres healthcheck fails repeatedly:** the volume may be wedged. Fix with `docker compose down -v` to wipe the named volume, then `docker compose up --build`.
- **LLM features need a real Gemini key.** The placeholder string `test-key-for-development` will fail with a 500/503 from any agent endpoint — paste a real key into `.env`.

### Run tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```

### Reset the database

```bash
docker compose down -v && docker compose up --build
```

Wipes the Postgres volume; alembic migrations re-run on next startup.

### Stop

`Ctrl+C` in the foreground terminal, then:

```bash
docker compose down
```

For more detail (alembic, manual db inspection, debugging agents, password reset), see [`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md).

---

## User Stories / Product Backlog

### Epicul 1: Înregistrare & Dashboard

**User Story 1.0: Autentificare și Creare Cont**

- **Descriere**: Ca utilizator nou, vreau să îmi creez un cont și să mă autentific (prin Email/Parolă, Google sau LinkedIn), astfel încât datele și CV-urile mele să fie salvate în siguranță.
- **Criterii de acceptare**:
  - Utilizatorul poate crea un cont cu o parolă validă (minim 8 caractere).
  - Parola este criptată (hashed) în baza de date.
  - Sesiunea utilizatorului persistă pe dispozitiv pe bază de token (ex: JWT).

---

**User Story 1.1: Încărcare și Parsare Automată CV de bază**

- **Descriere**: Ca student, vreau să încarc CV-ul meu de bază (PDF sau Docx), astfel încât agentul **CV Profiler** să îl proceseze automat și să extragă structurat toate datele esențiale, fără nicio intervenție manuală din partea mea.
- **Criterii de acceptare**:
  - Interfața permite încărcarea de fișiere `.pdf` și `.docx`.
  - Agentul CV Profiler procesează automat fișierul imediat după încărcare și extrage structurat: abilități tehnice, experiență profesională (rol, companie, perioadă), educație și tehnologii utilizate.
  - Datele extrase sunt salvate automat în profilul utilizatorului din baza de date, fără niciun pas manual intermediar.
  - Interfața afișează un sumar vizual al datelor extrase (ex: listă de skills, experiențe identificate) exclusiv pentru confirmare — utilizatorul poate corecta eventuale erori de parsare, dar nu este obligat să completeze nimic de la zero.
  - În cazul în care CV Profiler nu poate extrage suficiente date (ex: CV bazat pe imagini/scan), sistemul afișează un mesaj de eroare clar și sugerează reîncărcarea unui fișier cu text selectabil.

---

**User Story 1.2: Definire Criterii Job Dorit**

- **Descriere**: Ca student, vreau să definesc criteriile pentru jobul dorit (ex: "Intern Frontend", "Remote", "React"), astfel încât agentul Job Scanner să găsească doar roluri relevante.
- **Criterii de acceptare**:
  - Utilizatorul poate salva titlul jobului, locația/tipul (remote/hibrid) și 3-5 cuvinte cheie.
  - Aceste preferințe se salvează în profilul utilizatorului din baza de date.

---

**User Story 1.3: Panou Principal (Dashboard)**

- **Descriere**: Ca utilizator, vreau un dashboard centralizat unde să văd joburile potrivite, procentul de compatibilitate și stadiul documentelor mele.
- **Criterii de acceptare**:
  - Afișează o listă/tabel cu joburile găsite.
  - Fiecare job are un indicator cu procentajul de potrivire.
  - Există butoane de acțiune pentru fiecare job: "Generează CV", "Generează Interviu".

---

### Epicul 2: Agentul Job Scanner

**User Story 2.1: Căutare Automată Joburi (Cron Job)**

- **Descriere**: Ca aplicant, vreau ca Job Scanner-ul să caute pe platforme la fiecare 24 de ore, ca să nu ratez oportunități noi.
- **Criterii de acceptare**:
  - Un proces automat rulează zilnic pe server.
  - Se conectează la un API de joburi sau face scraping legal pe baza criteriilor utilizatorilor.
  - Salvează descrierile noilor joburi (JD) în baza de date și le asociază utilizatorilor potriviți.

---

**User Story 2.2: Filtrare Joburi Duplicate / Aplicate**

- **Descriere**: Ca utilizator, vreau ca Job Scanner-ul să identifice și să elimine joburile duplicate sau la care am aplicat deja, astfel încât să văd doar oportunități noi și relevante în dashboard. Un job este considerat duplicat dacă are același URL **sau** aceeași combinație de "Nume Companie + Titlu Job + Descriere parțială" ca unul deja existent în sistem — chiar dacă provine de pe o platformă diferită (ex: același rol postat atât pe LinkedIn, cât și pe Indeed).
- **Criterii de acceptare**:
  - Sistemul verifică URL-ul și combinația "Nume Companie + Titlu Job + primele 200 de caractere din descriere" pentru a detecta duplicatele între platforme.
  - Joburile duplicate nu apar în lista principală; utilizatorul poate accesa o secțiune "Duplicate detectate" pentru verificare manuală dacă dorește.
  - Utilizatorul are un buton "Am aplicat" pe fiecare job, care mută jobul într-o secțiune separată "Istoric Aplicații".
  - Joburile din "Istoric" nu mai apar în lista principală și nu mai sunt procesate de agenți.

---

### Epicul 3: Agentul CV Optimizer

**User Story 3.1: Rescriere CV pentru Filtrele ATS**

- **Descriere**: Ca aplicant, vreau ca CV Optimizer-ul să analizeze descrierea jobului și să rescrie punctele din CV-ul meu pentru a reflecta cuvintele cheie cerute.
- **Criterii de acceptare**:
  - LLM-ul primește un prompt restrictiv care interzice inventarea de experiență.
  - Sistemul returnează un JSON sau text curat cu punctele de experiență reformulate.
  - Utilizatorul poate previzualiza și edita textul returnat.

---

**User Story 3.2: Generare Scrisoare de Intenție (Cover Letter)**

- **Descriere**: Ca aplicant, vreau să generez o Scrisoare de Intenție personalizată pe baza companiei și rolului.
- **Criterii de acceptare**:
  - Generează un text de 3-4 paragrafe.
  - Include automat numele companiei extrase de Job Scanner și rolul vizat.

---

**User Story 3.3: Export Documente în PDF**

- **Descriere**: Ca utilizator, vreau să export aceste documente ca PDF-uri formatate corect, gata de încărcare pe site-ul angajatorului.
- **Criterii de acceptare**:
  - Textul generat de LLM este convertit într-un șablon PDF vizual curat.
  - Fișierul se descarcă automat pe dispozitivul utilizatorului.

---

### Epicul 4: Agentul Interview Coach

**User Story 4.1: Generare Întrebări de Interviu**

- **Descriere**: Ca și candidat, vreau ca Interview Coach să genereze 5-7 întrebări tehnice și comportamentale bazate strict pe descrierea jobului.
- **Criterii de acceptare**:
  - Se afișează 3 întrebări tehnice și 2 comportamentale deduse din JD.
  - Se oferă un scurt ghid despre cum ar trebui să sune răspunsul ideal.

---

**User Story 4.2: Fișă de Recapitulare (Cheat Sheet)**

- **Descriere**: Ca și candidat, vreau o "fișă de recapitulare" a tehnologiilor de bază menționate în job, pentru a mă pregăti rapid.
- **Criterii de acceptare**:
  - Extrage cuvintele cheie tehnice din JD.
  - Generează câte un paragraf de definiție/concept esențial pentru fiecare tehnologie.

---

### Epicul 5: Competitive Benchmarking

**User Story 5.1: Calculare Scor de Competitivitate**

- **Descriere**: Ca utilizator, vreau un scor (1-100) care să reflecte cât de puternic este CV-ul meu comparativ cu cerințele jobului și piața, calculat exclusiv pe baza datelor agregate și anonimizate, în conformitate cu reglementările GDPR.
- **Criterii de acceptare**:
  - Sistemul compară cuvintele cheie și anii de experiență din CV cu cele din JD.
  - Scorul este calculat pe baza datelor agregate și anonimizate ale altor utilizatori; nicio informație personală identificabilă nu este utilizată sau expusă în cadrul calculului.
  - Platforma obține consimțământul explicit al utilizatorului (opt-in) înainte de a include datele sale în calculele de benchmarking colectiv.
  - Utilizatorul poate opta oricând să se retragă din benchmarking (opt-out), fără a pierde accesul la celelalte funcționalități ale platformei.
  - Scorul este afișat grafic în interfață.

---

**User Story 5.2: Comparare Scor cu Candidați de Același Nivel și Nișă**

- **Descriere**: Ca utilizator, vreau ca scorul meu să fie comparat **exclusiv** cu candidați de același nivel de senioritate (Intern, Junior, Mid sau Senior), pentru a obține un benchmark relevant și corect. Pentru nivelurile Mid și Senior, compararea se face suplimentar pe nișa/domeniul de activitate (ex: Frontend, Backend, DevOps, Data Science), astfel încât să nu fiu comparat cu persoane din arii tehnice diferite.
- **Criterii de acceptare**:
  - Utilizatorul selectează explicit nivelul său de senioritate la configurarea profilului: Intern, Junior, Mid sau Senior.
  - Algoritmul de scoring folosește **exclusiv** datele candidaților cu același nivel de senioritate selectat; comparațiile între niveluri diferite (ex: Junior vs. Senior) sunt complet excluse.
  - Pentru nivelurile **Mid** și **Senior**, utilizatorul selectează și nișa sa de activitate (ex: Frontend, Backend, Mobile, DevOps, Data Science, QA etc.), iar compararea se face strict în cadrul aceleiași nișe.
  - Interfața afișează clar grupul de referință folosit pentru comparare (ex: *"Ești comparat cu 1.240 de candidați Junior din nișa Frontend"*).
  - Dacă numărul de candidați din același grup (nivel + nișă) este insuficient pentru un benchmark valid (ex: sub 30 de persoane), sistemul afișează un avertisment și nu generează un scor comparativ.

---

**User Story 5.3: Recomandări de Abilități și Cuvinte Cheie în Funcție de Domeniu**

- **Descriere**: Ca utilizator, vreau să primesc recomandări personalizate de abilități lipsă și cuvinte cheie relevante, filtrate în funcție de domeniul și nișa mea de activitate, astfel încât sugestiile să fie acționabile și specifice contextului meu profesional.
- **Criterii de acceptare**:
  - Sistemul identifică diferențele dintre CV-ul utilizatorului și cerințele din JD, filtrate prin lentila domeniului selectat (ex: pentru Frontend se recomandă skill-uri precum TypeScript, Accessibility, Web Performance — nu competențe de DevOps sau Data Science).
  - Se afișează un **Top 3 abilități lipsă**, fiecare însoțită de o scurtă justificare (ex: *"TypeScript apare în 78% din joburile Junior Frontend din zona ta"*).
  - Se afișează o secțiune separată **"Cuvinte cheie recomandate pentru CV"**, cu termeni și expresii specifice domeniului care cresc vizibilitatea în filtrele ATS (ex: *"component-driven development"*, *"responsive design"*, *"CI/CD pipelines"*).
  - Recomandările se actualizează dinamic la fiecare job nou analizat, reflectând cerințele specifice ale acelui JD în contextul domeniului utilizatorului.