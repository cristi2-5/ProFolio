# rules.md: Autonomous Agent System Instructions

## 🤖 1. Core Agent Workflow Loop
For every prompt or task assigned by the user, the agent must strictly execute the following sequence:

1. **Context Initialization:** Read `rules.md` (this file) and `project_index.md` to establish constraints and project structure.
2. **Context Scoping:** Identify the absolute minimum set of relevant files based on `project_index.md`. Do not read or load the entire repository.
3. **Plan Proposal:** Present a step-by-step plan to the user. Include the target files, the architectural approach, and expected outcomes.
4. **User Approval:** Wait for the user to approve or modify the plan before writing any code.
5. **Execution:** Implement the agreed-upon changes, strictly adhering to the Coding Standards and Git Source Control sections.
6. **Testing & QA:** Write and run automated tests for the new implementation.
7. **Logging & Audit:** Generate an entry in `log.txt` detailing the changes, security audit, and test results.

---

## 🏗 2. Project Indexing & State Management
To maintain an efficient context window, the agent must manage a living index of the project.

* **File Tracking:** Maintain a `project_index.md` file at the root of the project.
* **Update Trigger:** Update `project_index.md` immediately whenever a file is created, deleted, renamed, or substantially heavily modified in its purpose.
* **Format Requirement:** Every entry in `project_index.md` must include the file path, a one-sentence summary of its purpose, and its primary dependencies.

---

## 🛠 3. Coding Standards & Architecture
The agent must generate production-ready, maintainable code.

* **Modularity:** Adhere to SOLID principles. Functions and classes must have a single responsibility.
* **DRY Principle:** "Don't Repeat Yourself." Abstract repetitive logic into shared utility functions.
* **Documentation:** All public functions, classes, and complex logic blocks must include language-standard docstrings (e.g., JSDoc, PEP 257) detailing parameters, return types, and side effects.
* **Error Handling:** Implement robust try/catch blocks or error boundary patterns. Never silently swallow errors; log them explicitly or raise meaningful exceptions.
* **Formatting:** Conform to the standard style guide of the target language (e.g., Prettier for JS/TS, Black for Python, gofmt for Go).

---

## 🌳 4. Git & Source Control Management
All changes must be safely version-controlled using standard Git workflows.

* **Branch Creation:** Never work directly on the `main` or `master` branch.
* **Branch Naming Conventions:** Use `feat/` for new features, `fix/` for bug fixes, `docs/` for documentation, `test/` for testing additions, and `refactor/` for code structure changes (e.g., `feat/user-authentication-flow`).
* **Commit Granularity:** Make small, atomic commits that represent a single logical change.
* **Commit Messages:** Follow Conventional Commits format: `<type>(<scope>): <subject>`. Example: `feat(auth): implement JWT token validation`.
* **Pull Requests:** Upon task completion, summarize the changes, reference the original user request, and create a Pull Request (PR) against the main branch.

---

## 🧪 5. Quality Assurance & Automated Testing
The agent must validate its own code before considering a task complete.

* **Test Driven Mindset:** Write tests alongside or immediately following feature development.
* **Core Functionality Testing:** Ensure the "happy path" executes exactly as expected.
* **Edge Case Testing:** Aggressively test boundary conditions, zero values, extremely large inputs, and invalid data types.
* **Failure State Testing:** Verify that error handling triggers properly when dependencies fail or inputs are malformed.

---

## 🛡 6. Security & Code Audit Review
Before finalizing the `log.txt` entry, the agent must perform a static analysis of the modified code.

* **Vulnerability Scan:** Check for common OWASP risks such as SQL Injection, Cross-Site Scripting (XSS), insecure deserialization, and hardcoded credentials.
* **Performance Check:** Analyze algorithmic complexity (Time/Space). Suggest alternatives if loops are nested inefficiently or database queries lack optimization.
* **Dependency Check:** Ensure no deprecated or unverified third-party libraries were introduced.

---

## 📝 7. Comprehensive Logging Protocol
At the end of every task execution, append a strictly formatted entry to `log.txt`. 

```text
==================================================
TIMESTAMP: [YYYY-MM-DD HH:MM:SS]
TASK/PROMPT: [Brief summary of the user's request]
BRANCH: [Branch Name]
PR STATUS: [Draft / Submitted / Merged]

--- FILES MODIFIED ---
- [File Path 1]: [Brief reason for change]
- [File Path 2]: [Brief reason for change]

--- ARCHITECTURE & LOGIC CHANGES ---
[Detailed explanation of what was built, refactored, or fixed]

--- AUDIT & VERIFICATION REVIEW ---
BUGS/KNOWN ISSUES: [List any unresolved edge cases or state "None"]
SECURITY VULNERABILITIES: [Results of the security scan or state "None detected"]
PERFORMANCE OPTIMIZATIONS: [Details on algorithm improvements or state "No changes required"]
MAINTAINABILITY IMPROVEMENTS: [Suggestions for future refactoring]

--- TEST COVERAGE ---
TEST FILES ADDED/MODIFIED: [List of test files]
SCENARIOS COVERED: [Happy path, Error X, Edge Case Y]
TEST STATUS: [Passed / Failed]
==================================================