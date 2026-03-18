# Auto-Apply: Job Hunter & Interview Strategist

## Descrierea Aplicației

Auto-Apply este o platformă inteligentă creată pentru a automatiza și eficientiza procesul de căutare a unui loc de muncă sau internship. Construită pentru a combate "oboseala aplicantului", aplicația folosește o arhitectură bazată pe agenți AI pentru a prelua sarcinile repetitive și consumatoare de timp.

Sistemul permite utilizatorilor să își încarce CV-ul de bază și să definească rolul dorit. Din acel moment, trei agenți autonomi preiau controlul:
1. **Job Scanner:** Caută zilnic pe platformele de recrutare și aduce cele mai relevante oportunități direct într-un panou centralizat.
2. **CV Optimizer:** Analizează descrierea fiecărui job (JD) și reformulează dinamic CV-ul și Scrisoarea de Intenție pentru a trece de filtrele ATS (Applicant Tracking System), păstrând strictețea datelor reale ale candidatului.
3. **Interview Coach:** Generează materiale de pregătire personalizate (întrebări tehnice, comportamentale și fișe de recapitulare) bazate exact pe tehnologiile cerute de angajator.

În plus, aplicația oferă un sistem de evaluare comparativă (Competitive Benchmarking) pentru a arăta candidaților unde se situează față de cerințele pieței și ce abilități trebuie să mai dezvolte.

---

## User Stories / Product Backlog

### Epicul 1: Înregistrare & Dashboard

**User Story 1.0: Autentificare și Creare Cont**
* **Descriere:** Ca utilizator nou, vreau să îmi creez un cont și să mă autentific (prin Email/Parolă, Google sau LinkedIn), astfel încât datele și CV-urile mele să fie salvate în siguranță.
* **Criterii de acceptare:**
    * Utilizatorul poate crea un cont cu o parolă validă (minim 8 caractere).
    * Parola este criptată (hashed) în baza de date.
    * Sesiunea utilizatorului persistă pe dispozitiv pe bază de token (ex: JWT).

**User Story 1.1: Încărcare și Parsare CV de bază**
* **Descriere:** Ca student, vreau să încarc CV-ul meu de bază (PDF sau Docx), astfel încât sistemul să îmi cunoască abilitățile și experiența.
* **Criterii de acceptare:**
    * Interfața permite încărcarea de fișiere .pdf și .docx.
    * Backend-ul extrage cu succes textul din fișier.
    * Interfața afișează un mesaj de succes și o listă scurtă cu datele extrase pentru validare.

**User Story 1.2: Definire Criterii Job Dorit**
* **Descriere:** Ca student, vreau să definesc criteriile pentru jobul dorit (ex: "Intern Frontend", "Remote", "React"), astfel încât agentul Job Scanner să găsească doar roluri relevante.
* **Criterii de acceptare:**
    * Utilizatorul poate salva titlul jobului, locația/tipul (remote/hibrid) și 3-5 cuvinte cheie.
    * Aceste preferințe se salvează în profilul utilizatorului din baza de date.

**User Story 1.3: Panou Principal (Dashboard)**
* **Descriere:** Ca utilizator, vreau un dashboard centralizat unde să văd joburile potrivite, procentul de compatibilitate și stadiul documentelor mele.
* **Criterii de acceptare:**
    * Afișează o listă/tabel cu joburile găsite.
    * Fiecare job are un indicator cu procentajul de potrivire.
    * Există butoane de acțiune pentru fiecare job: "Generează CV", "Generează Interviu".

---

### Epicul 2: Agentul Job Scanner

**User Story 2.1: Căutare Automată Joburi (Cron Job)**
* **Descriere:** Ca aplicant, vreau ca Job Scanner-ul să caute pe platforme la fiecare 24 de ore, ca să nu ratez oportunități noi.
* **Criterii de acceptare:**
    * Un proces automat rulează zilnic pe server.
    * Se conectează la un API de joburi sau face scraping legal pe baza criteriilor utilizatorilor.
    * Salvează descrierile noilor joburi (JD) în baza de date și le asociază utilizatorilor potriviți.

**User Story 2.2: Filtrare Joburi Duplicate / Aplicate**
* **Descriere:** Ca utilizator, vreau ca Job Scanner-ul să marcheze joburile duplicate sau la care am aplicat deja.
* **Criterii de acceptare:**
    * Sistemul verifică URL-ul și combinația "Nume Companie + Titlu Job" pentru a preveni duplicatele.
    * Utilizatorul are un buton "Am aplicat", care mută jobul într-o secțiune separată "Istoric".

---

### Epicul 3: Agentul CV Optimizer

**User Story 3.1: Rescriere CV pentru Filtrele ATS**
* **Descriere:** Ca aplicant, vreau ca CV Optimizer-ul să analizeze descrierea jobului și să rescrie punctele din CV-ul meu pentru a reflecta cuvintele cheie cerute.
* **Criterii de acceptare:**
    * LLM-ul primește un prompt restrictiv care interzice inventarea de experiență.
    * Sistemul returnează un JSON sau text curat cu punctele de experiență reformulate.
    * Utilizatorul poate previzualiza și edita textul returnat.

**User Story 3.2: Generare Scrisoare de Intenție (Cover Letter)**
* **Descriere:** Ca aplicant, vreau să generez o Scrisoare de Intenție personalizată pe baza companiei și rolului.
* **Criterii de acceptare:**
    * Generează un text de 3-4 paragrafe.
    * Include automat numele companiei extrase de Job Scanner și rolul vizat.

**User Story 3.3: Export Documente în PDF**
* **Descriere:** Ca utilizator, vreau să export aceste documente ca PDF-uri formatate corect, gata de încărcare pe site-ul angajatorului.
* **Criterii de acceptare:**
    * Textul generat de LLM este convertit într-un șablon PDF vizual curat.
    * Fișierul se descarcă automat pe dispozitivul utilizatorului.

---

### Epicul 4: Agentul Interview Coach

**User Story 4.1: Generare Întrebări de Interviu**
* **Descriere:** Ca și candidat, vreau ca Interview Coach să genereze 5-7 întrebări tehnice și comportamentale bazate strict pe descrierea jobului.
* **Criterii de acceptare:**
    * Se afișează 3 întrebări tehnice și 2 comportamentale deduse din JD.
    * Se oferă un scurt ghid despre cum ar trebui să sune răspunsul ideal.

**User Story 4.2: Fișă de Recapitulare (Cheat Sheet)**
* **Descriere:** Ca și candidat, vreau o "fișă de recapitulare" a tehnologiilor de bază menționate în job, pentru a mă pregăti rapid.
* **Criterii de acceptare:**
    * Extrage cuvintele cheie tehnice din JD.
    * Generează câte un paragraf de definiție/concept esențial pentru fiecare tehnologie.

---

### Epicul 5: Competitive Benchmarking

**User Story 5.1: Calculare Scor de Competitivitate**
* **Descriere:** Ca utilizator, vreau un scor (1-100) care să reflecte cât de puternic este CV-ul meu comparativ cu cerințele jobului și piața.
* **Criterii de acceptare:**
    * Sistemul compară cuvintele cheie și anii de experiență din CV cu cele din JD.
    * Afișează scorul grafic în interfață.

**User Story 5.2: Filtrare Competiție după Nivel de Experiență**
* **Descriere:** Ca utilizator, vreau ca scorul meu să fie calculat strict pe baza nivelului meu (Intern, Junior, Mid, Senior).
* **Criterii de acceptare:**
    * Algoritmul de scorare ignoră cerințele specifice altor niveluri de senioritate dacă nu se potrivesc profilului selectat.

**User Story 5.3: Recomandări Top 3 Abilități Lipsă**
* **Descriere:** Ca utilizator, vreau să văd un top 3 al celor mai cerute abilități care îmi lipsesc de pe CV.
* **Criterii de acceptare:**
    * Sistemul identifică diferențele majore dintre CV și JD.
    * Afișează o secțiune dedicată cu abilitățile lipsă pe care utilizatorul ar trebui să le dobândească.