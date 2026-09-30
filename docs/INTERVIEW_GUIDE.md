# Explain the work honestly

Use the actual code and your own commits as evidence. These are practice questions and technical explanations, not claims that you independently authored the baseline.

## A short demo structure

1. Explain the user's problem in one sentence.
2. Show the main workflow using synthetic data.
3. Show a failure case and the application's response.
4. Open the function and test behind the behavior.
5. Describe one limitation and the improvement you personally made.

## Questions to practice

| Project | Question | Evidence to explain |
| --- | --- | --- |
| SmartFind | What happens if two sales arrive at the same time? | `BEGIN IMMEDIATE` takes the SQLite write lock before checking stock. The stock change and ledger entry share one transaction. A concurrent test ensures only one 30-unit sale succeeds against 48 units. |
| AttendFlow | Why validate duplicates in the database? | `UNIQUE(student_id,event_id)` prevents duplicate records even when two requests race. The HTTP boundary maps integrity conflicts to 409. |
| AttendFlow | How do you show students who never checked in? | The report starts from all students and uses a `LEFT JOIN` on the selected event. A missing attendance row becomes Absent. |
| PesoLens | Why store cents rather than floating-point amounts? | Decimal input is validated and converted to integer cents. Aggregation stays exact; formatting happens when exporting or rendering. |
| PesoLens | What if row 20 of an import is invalid? | Every row is validated before insertion. No rows are saved from that file if validation fails. A test checks that the database is unchanged. |
| AccessPath | Why remove unsuitable edges before routing? | Routing operates only on feasible segments. Dijkstra chooses the minimum distance among them; it never trades a hard constraint for a shorter route. |
| AccessPath | What if there is no feasible route? | The result has `found: false`, an empty path and no distance. The UI asks the user to change preferences or reopen a path. |
| MiniLang | How is `2 + 3 * 4` parsed? | Precedence climbing makes multiplication bind more tightly. The AST and result tests demonstrate this behavior. |
| MiniLang | Why not call Python `eval`? | The interpreter visits only the defined AST node types. Source cannot access files, imports or networking. Token, nesting, execution and output limits bound the work. |
| All | Is this production-ready? | No. It is a local MVP with synthetic data and no accounts. Explain what proper authentication, deployment, backups and migrations would require. |

## Describe your contribution

After extending a project, write down the exact feature you implemented, the failure case your test covers, and one design decision you made. Mention AI assistance accurately when asked. Avoid inventing users, deployments, business impact, team roles or performance measurements.

## Before applying

You should be able to run the project from a fresh download, explain its data model, modify a feature without guessing, reproduce a bug, explain one test and identify its limitations. A smaller project you understand is easier to discuss than a large project you cannot explain.
