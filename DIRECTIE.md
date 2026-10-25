# Fișa de direcție — atelierul 1

> **Inginerie Software 2026–27** · temă opțională, nu se notează.
> Atelierul 1 (S5, 26–30 oct) confirmă direcția în care vă duceți proiectul. Echipele care vin cu fișa au o discuție mai scurtă și mai precisă.
>
> **Cum:** copiați fișierul în rădăcina repo-ului ca `DIRECTIE.md`, completați-l și faceți commit înainte de slotul vostru de atelier. Veniți la atelier cu el în repo.
> **Atelierul:** vom posta un calendar; fiecare echipă își rezervă slotul în intervalul de 4 ore, cu Rareș și Petru.
> **Lungime:** cel mult două pagini. Puncte scurte, nu eseuri.
> **Când:** secțiunile 1–6 după cursul 2 (S3); secțiunile 7–8 după cursul 3 (S4).
> **AI:** permis și declarat (în mesajul de commit), ca la orice livrabil. La atelier, fiecare membru trebuie să poată explica orice rând de aici.
>
> Indicațiile sunt comentarii `<!-- ... -->`: nu apar pe GitHub, le puteți lăsa sau șterge.

| | |
|---|---|
| **Echipa** | ProFolio |
| **Membri** | Filote Alexandru-Ionuț, Alexandru Nicolas Negrisan, Roland Boldesco, Stoian Andrei-Cristian, Afanasii Munteanu. |
| **Repo** | https://github.com/inginerie-software-26-27/is2627-proiect-group-19 |

---

## 1. Sistemul, așa cum e acum (as-is)

- **Ce face, pentru cine:** aplicație web pentru studenți/absolvenți IT care caută job. Încarci CV-ul (PDF/DOCX), un agent LLM (Gemini) îl parsează; un scanner aduce joburi de pe Adzuna și le punctează; agenții rescriu CV-ul pentru ATS, scriu cover letter (export PDF), generează pregătire de interviu și un benchmark anonimizat față de alți candidați (opt-in GDPR). Stack: FastAPI + PostgreSQL + React/Vite, Docker Compose, GitHub Actions.
- **Ce merge** auth email/parolă + JWT; upload + parsare CV; scan Adzuna + dedup + scor; listă joburi cu filtre/paginare/status („Am aplicat” = doar un status, nu se trimite nimic); optimizare CV + cover letter + PDF; interview coach (3+2 întrebări + cheat sheet); feedback.
- **Pe jumătate:** editarea datelor parsate (UI trimite `PATCH`, backend are `PUT` → 405); salvarea CV-ului/cover letter editate (rute inexistente → 404); nume fișier și date personale neafișate (câmpuri diferite backend/UI); preferințe salariu/oraș colectate dar ignorate; responsive doar meniul (1 media query, 585 stiluri inline, `JobDetail.jsx` 2.160 linii); benchmarking cere 30 de peers (merge doar cu date seed, doar junior); SSE/async există în backend fără consumator; pagini legale stub, cu afirmație falsă („nu trimitem date terților” — CV-ul merge la Google).
- **Nu merge / lipsește:** vizualizare sau preview al CV-ului original (fișierul e salvat, nimic nu-l servește); ștergere CV din UI; SSO (butoane disabled); cover letter cu „[Your Name]” (parser-ul nu produce `personal_info`); CV Optimizer a picat 3/3 la singura calibrare (JSON malformat); CI „verde”, dar pytest/flake8/mypy/scanările de securitate sunt non-blocante (ultimul run pe main: pytest exit 1) și `main` n-are branch protection;
- **Cum am aflat:** Am facut QA manual functional si vizual la aplicatie; AI:am citit tot codul (backend 13,5k LOC, frontend 10,8k), README, docs, `log.txt`, istoricul git (134 commits, 5 autori); am rulat local: vitest 25/25, eslint 0 erori, build OK, black/isort OK, flake8 206 abateri, mypy 114 erori, pytest fără Postgres (77/77 pe subsetul fără DB), evals 30/30; `gh run list` pe main. 

## 2. Direcția (to-be)

| # | Obiectiv | De ce acum | Cum știm că l-am atins |
|---|---|---|---|
| O1 | **Reparăm și închidem fluxul CV-ului**: upload corect → vezi CV-ul original → corectezi datele parsate → agenții folosesc corecțiile → pool de skills din mai multe CV-uri (lista noastră: CV în app, vizionare, preview, editare, mai multe CV-uri) | E calea principală a produsului și e ruptă în 4 locuri (405/404, câmpuri greșite, fără preview); fără ea nimic din ce urmează nu se poate demonstra | Test E2E (Playwright, LLM în mod mock) upload → vezi → editezi → optimizezi → export trece în CI; 0 apeluri din frontend către rute inexistente (test de contract pe OpenAPI);|
| O2 | **Schimbăm interfața**: strat de componente + tokens (light/dark), responsive pe telefon, principii Apple HIG | 585 stiluri inline, o singură media query, taburi inaccesibile pe mobil; studenții folosesc telefonul; UI-ul e ce vede evaluatorul | Toate paginile utilizabile la 375 px fără scroll orizontal (Playwright); Lighthouse accessibility ≥ 90 pe Dashboard/Jobs/JobDetail/Resumes; 0 `style={{` în pagini (regulă ESLint);|
| O3 | **Întărim calitatea și infrastructura**: CI blocant + branch protection, audit și rotire chei, compose „prod” + test de încărcare (locust); Kubernetes doar dacă rămâne timp | CI-ul verde nu dovedește nimic azi; refactorul din O1/O2 fără plasă de siguranță aduce regresii; cheie în istoric public | PR cu test picat nu poate fi merge-uit; gitleaks 0 findings; locust 50 useri, p95 < 500 ms pe `GET /api/jobs`, 0 erori 5xx, rulat în CI pe main;|

**Opțional / research (nu intră în O1–O3; le luăm doar dacă rămâne timp):**

- **Scraper propriu** în locul Adzuna — *research*: spike de 2 zile pe API-uri gratuite și pe ce permit ToS-urile (LinkedIn/Indeed interzic scraping-ul HTML); decizie la S8. Facem oricum interfața `JobProvider`, ca orice sursă nouă să fie un adaptor.
- **SSO cu Google** — *opțional*: gratuit, ~3–4 zile; cere URL public pentru callback, parolă opțională în DB, ștergere cont fără parolă. LinkedIn: gratuit, dar cere pagină de companie + review.
- **Bulk apply** — *research*: azi „Apply” nu trimite nimic nicăieri; auto-submit = automatizare per site cu risc legal; varianta realistă e „generează materiale pentru N joburi”, limitată de cota Gemini (20 cereri/zi pe cheie).
- **Recenzii companii** — *opțional*: pas mic acum (rezultat per aplicație: interviu/ofertă/respins pe `UserJob`); entitatea Company + moderare + k-anonimitate doar dacă avem utilizatori care produc date.
- **Domenii non-IT** — *research*: catalogul tehnic, scoringul și fixture-urile sunt 100% IT; estimăm ce înseamnă o taxonomie per domeniu, decizie după O1.

## 3. Stakeholderii

| Cine | Ce vrea de la sistem | Cum aflăm ce vrea |
|---|---|---|
| Studenți/absolvenți IT la primul job (utilizatorii) | CV parsat corect, joburi relevante, materiale gata de trimis, de pe telefon | Test de utilizare cu 5–8 colegi; personas MDS; widget-ul de feedback existent |
| Echipa (5 dev) | Cod modificabil fără să rupă restul, CI de încredere, ore predictibile | Retro la 2 săptămâni; PR-uri și CI în repo |
| Profesorii/evaluatorii (Rareș, Petru) | Cerințe lângă cod și teste, direcție justificată, fiecare membru explică | Atelier 1, acest fișier |
| Furnizorii externi: Google (Gemini), Adzuna | Respectarea cotelor (5 RPM / 20 RPD; 250 req/lună) și a ToS | Documentația API; calibrarea din 24 mai (20 RPD arse într-o rulare) |
| Persoanele ale căror date sunt în CV-uri (GDPR) | Consimțământ, ștergere completă (azi fișierele rămân pe disc la ștergerea contului), politică de confidențialitate adevărată | Scenarii GDPR (ștergere, export); politica actuală contrazice codul |

## 4. Resursele noastre

| Resursă | Ce avem, realist | Ce ne lipsește |
|---|---|---|
| **Oameni** | 5 membri × 2 h/săpt = 10 h/săpt în echipă, ~90 h până la S14 (≈ 11 zile-om); absențe: nu există „nu pot”, ci doar „nu vreau” | Un owner per obiectiv; ritm constant, nu burst-uri |
| **Cunoștințe** | Claude Code, Python/FastAPI/SQLAlchemy, React, Postgres, Docker Compose, GitHub Actions, prompting Gemini, pytest/vitest | Prima dată: design system/HIG, Playwright E2E, locust, OAuth, Kubernetes (nimeni → risc 9), legalitatea scraping-ului |
| **Tehnice** | Stack-ul de mai sus; medii: doar local (compose); CI: 3 workflow-uri / 17 joburi, majoritatea neblocante; hosting: niciunul; externe: Gemini free, Adzuna free, GitHub public | Un mediu public (free tier) pentru teste cu utilizatori și SSO; Redis pentru limite/cache partajate; venv local reparat (3.14 vs 3.13) |
| **Financiare** | 0 lei | Opțional ~5 $ credit Gemini (deblochează calibrarea și evals-urile LLM); hosting free tier |
| **Acces la AI** | O singură cheie Gemini free (5 RPM / 20 RPD), împărțită de toți utilizatorii aplicației; Claude Code/Gemini; Nu punem în model: CV-uri reale ale altor persoane fără acord, chei, parole, conținutul `.env` | Chei per membru sau tier plătit; mod mock (`test-` key) pentru CI/E2E |

## 5. Fezabilitate

| Întrebare | Da / Nu / Nu știm | De ce |
|---|---|---|
| Contribuie direcția la ce vor stakeholderii de la secțiunea 3? | Da | O1 e exact fluxul cerut de US 1.1 și verificat de evaluatori; O2 = „de pe telefon”; O3 = încredere + GDPR |
| Se poate face până la final de semestru, cu resursele de la secțiunea 4? | Da | 5 membri × 2 h/săpt, un owner per obiectiv; O1 se sprijină pe rute backend care există deja, O3 e în mare parte configurare, O2 merge pagină cu pagină; prioritățile must/should din secțiunea 7 spun ce lăsăm ultimul dacă rămânem în urmă |
| Se integrează cu ce există deja în sistem și în jurul lui? | Da | Totul pe stack-ul existent; rutele backend pentru O1 există deja (`PUT`, `DELETE`, `activate`); doar SSO și hosting-ul public cer ceva nou |

## 6. Primele cinci riscuri

| # | Risc | Tip | Impact | Prob. | Scor | Strategie |
|---|---|---|---|---|---|---|
| R1 | Redesign-ul (O2) înghite semestrul: fiecare pagină e stil inline, `JobDetail.jsx` are 2.160 linii | estimation | 3 | 3 | 9 | minimize: întâi stratul de componente, apoi pagină cu pagină; contingency: livrăm doar Dashboard/Jobs/JobDetail/Resumes |
| R2 | Cota Gemini free (20 cereri/zi, o cheie pentru toți) blochează demo-ul, testele și calibrarea | technology | 3 | 3 | 9 | avoid: E2E/CI pe mod mock; minimize: cache + chei per membru + 5 $ credit pentru demo |
| R3 | Partea de research (scraper propriu, bulk apply, domenii non-IT) se dovedește nefezabilă: ToS-urile interzic scraping-ul, auto-submit are risc legal, n-avem utilizatori non-IT | requirements | 2 | 3 | 6 | avoid: rămân în afara O1–O3; contingency: API-uri oficiale prin `JobProvider`, „materiale pentru N joburi” în loc de auto-submit |
| R4 | AI-ul degenerează: CV-uri/cover letter cu experiență inventată, placeholder-e („[Your Name]”), JSON malformat sau text jenant trimis angajatorului (la calibrare: 3/3 eșecuri, placeholder-e în 2/2 scrisori) | technology | 3 | 2 | 6 | minimize: set „golden” de CV×JD cu output de referință (pornim de la cele 15 perechi din `evals/fixtures`), evals deterministe + LLM-judge blocante în CI la orice schimbare de prompt/model, detectorul de fabricații afișat în UI; contingency: utilizatorul confirmă `changes_summary` înainte de export |
| R5 | Confidențialitate și abuz: CV-urile (date personale) ajung la alt utilizator sau la un terț, ori aplicația e scrapuită / pusă jos (DDoS, upload-uri în masă, epuizarea cotelor LLM/Adzuna) | technology | 3 | 2 | 6 | avoid: ownership pe fiecare rută cu teste IDOR (inclusiv pe fișierul CV), security headers + rate limit global pe Redis (azi doar pe câteva rute, în memorie), cotă per user pe upload/LLM, ștergere completă la ștergerea contului, gitleaks; contingency: Cloudflare free (WAF, anti-bot) în fața aplicației |

## 7. Cerințele candidate (după S4)

| # | Cerința | Prioritate | Tip | Sursa · confirmată de | De ce (rationale) | Cum verificăm |
|---|---|---|---|---|---|---|
| C1 | Utilizatorul își poate vedea CV-ul original (PDF/DOCX) din aplicație; alt utilizator primește 403 | must | F | Lista echipei + US 1.1 · *de confirmat la atelier* | Fișierul e salvat dar e „write-only”; fără el nu poți verifica ce a parsat agentul | pytest: `GET /api/resumes/{id}/file` → 200 + content-type corect, alt user → 403; Playwright: preview vizibil după upload |
| C2 | Utilizatorul poate corecta toate datele parsate (contact, skills, experiență, educație) și corecțiile ajung la agenți | must | F | US 1.1 criteriul 4 · confirmată de README | Azi salvarea dă 405; `parsed_data` e un dict nevalidat | pytest: `PUT` cu `ParsedCVData` valid → 200, invalid → 422; E2E: skill adăugat apare în output-ul `/optimize` |
| C3 | Upload-ul afișează corect numele fișierului și datele personale și distinge erorile 413 (cotă 5 CV-uri), 422 (parsare), 429 (cotă LLM) | must | F | Lista echipei („rezolvat adăugare CV”) · *de confirmat* | Cauzele raportate ca „nu merge” sunt mesaje lipsă și câmpuri cu nume diferite | Vitest pe `CVUpload`/`Resumes`; E2E cu fișier > 10 MB, al 6-lea CV, cheie `test-` |
| C4 | Mai multe CV-uri formează un profil agregat (uniune de skills cu sursa) folosit la scoring și optimizare | should | F | Lista echipei · *de confirmat* | Azi toți agenții citesc un singur CV „activ”; două rânduri active produc 500 | pytest: 2 CV-uri cu skills disjuncte → `GET /api/resumes/pool` = uniunea; scorul jobului se recalculează |
| C5 | Interfața respectă HIG și e responsive: funcționează pe telefon, tabletă și desktop fără scroll orizontal și cu toate acțiunile accesibile; componente comune (Button/Card/Tabs/Input), tokens light + dark, font de sistem, fără emoji ca icoane | must | NF produs (usability) | Lista echipei („design conform Apple”, „responsive pe toate”) · *de confirmat* | O singură media query și 585 stiluri inline fac orice schimbare globală imposibilă; taburile din JobDetail sunt tăiate pe mobil | Test automat pe cele trei lățimi de ecran pentru fiecare pagină; regulă de lint care interzice stilurile inline în pagini; audit de accesibilitate în CI; review HIG de 2 colegi |
| C6 | CI blochează merge-ul în `main` dacă pytest, flake8 sau coverage < 60 % pică; branch protection activă | must | NF organizațional | `docs/bug-reporting-and-pr-workflow.md` („CI verde obligatoriu”) · confirmată de echipă | Azi pasul pytest e `continue-on-error`, deci verde fără dovadă | `ci.yml` fără `continue-on-error` pe teste; un PR cu test picat rămâne blocat (verificat o dată) |
| C7 | Niciun secret în repo sau istoric; cheile Adzuna din istoric rotite; scanner de secrete blocant; cheile lipsă opresc pornirea cu mesaj clar | must | NF extern (securitate/legal) | Lista echipei („de verificat toate cheile”) + audit git · confirmată de istoric (commit `bd8444a`) | Repo public cu chei reale în istoric; cheile goale eșuează abia la primul apel | gitleaks în CI = 0 findings; pytest: start cu `OPENAI_API_KEY` gol → eroare la boot |
| C8 | API-ul susține 50 de utilizatori simultani cu p95 < 500 ms pe `GET /api/jobs` și 0 erori 5xx (LLM mock) | should | NF produs (performanță) | Lista echipei („benchmarks + simulat useri”) · *de confirmat* | Jobul „performance” din CI face 100 de `curl` pe `/health`; limitele și cache-ul sunt în memorie, per proces | Script locust în repo, rulat în CI pe main, cu praguri ca aserțiuni |
| C9 | Autentificare cu Google (OIDC); conturile fără parolă pot șterge contul | could | F | US 1.0 README · *de confirmat* | Gratuit, dar cere URL public + migrare (`password_hash` nullable) | E2E cu cont de test; pytest pe callback și pe `DELETE /me` fără parolă |

## 8. Primele trei architecture characteristics

| # | Architecture characteristic | Din ce cerință sau domain concern vine | Explicită / implicită |
|---|---|---|---|
| A1 | **Securitate și confidențialitate** (CV = date personale; IDOR, secrete, ștergere completă) | C7, US 5.1 (GDPR); domain concern: CV-ul pleacă la un terț (Google) | explicită |
| A2 | **Usability / responsiveness** pe mobil | C5; studenții aplică de pe telefon | explicită |
| A3 | **Reziliență la limitele serviciilor externe** (Gemini 20 RPD, Adzuna 250/lună): cache, coadă, degradare cu mesaj clar | C8, R2; n-a scris-o nimeni, dar orice demo sau test se lovește de ea | implicită |

## 9. Întrebări pentru atelier

- Scraper propriu: e acceptabil pentru curs să rămânem pe API-uri (Adzuna + un al doilea provider gratuit) și să documentăm de ce nu facem scraping?