**AI Code Integrity Auditor: A Governance Layer for Detecting**

**Integrity Failures in AI-Generated Code**

Gina Aulabaugh

PixelKraze, LLC

March 2026

**Abstract**

The proliferation of AI-assisted code generation tools has introduced a
new class of software defect that traditional static analysis tools are
not designed to detect. AI-generated code frequently exhibits patterns
of apparent correctness while concealing logical failures, incomplete
implementations, and fabricated references. This paper introduces the AI
Code Integrity Auditor, an open-source static analysis tool built on
Python and Streamlit that applies a rule-based detection engine to
identify nine categories of integrity failure in Python and JSON files.
The tool operates as a governance layer rather than a syntax validator,
targeting structural hallucinations, silent failure risks, placeholder
logic, terminal state failures, narrative state mismatches, control flow
drift, path-to-nowhere references, and schema drift. The paper describes
the theoretical basis for each detection category, the technical
architecture of the system, and the implications for AI-assisted
software development workflows.

*Keywords:* AI code generation, static analysis, software integrity,
hallucination detection, code governance

**Introduction**

The adoption of large language model (LLM)-based code generation tools
has accelerated rapidly across the software development industry. Tools
such as GitHub Copilot, ChatGPT, and similar systems now assist
developers in generating substantial portions of production codebases
(Chen et al., 2021). While these tools demonstrably increase development
velocity, they also introduce a category of defect that differs
fundamentally from traditional programming errors. Unlike syntax errors
or type mismatches that a compiler or linter can detect, AI-generated
defects often manifest as code that is syntactically valid and
superficially plausible but logically incorrect or structurally
fabricated (Liu et al., 2023).

This phenomenon has been described in the literature as *hallucination*,
a term borrowed from the study of LLM outputs to denote the generation
of content that is confident in tone but factually or functionally
incorrect (Ji et al., 2023). In the context of software, hallucinated
code may reference variables that do not exist, call functions that were
never defined, or implement logic that superficially resembles correct
behavior while failing to produce valid output under real conditions
(Perry et al., 2023).

Existing static analysis tools such as pylint, flake8, and mypy are well
suited to detecting syntactic violations, style deviations, and type
inconsistencies. However, they are not designed to identify the semantic
and logical failure patterns characteristic of AI-generated code (Beller
et al., 2016). A function that swallows all exceptions with a bare
*except* block, logs a success message, and returns nothing will pass
all existing linters without issue. Yet this function represents a
serious integrity failure in any production system.

The AI Code Integrity Auditor was designed to address this gap. It
provides a rule-based governance layer that analyzes Python and JSON
files for nine categories of integrity failure that are specifically
associated with AI-generated code patterns. The tool is implemented as a
local Streamlit application, operates entirely on standard Python
libraries, and is designed for use as a pre-deployment review step in
AI-assisted development workflows.

**Background and Related Work**

***AI Code Generation and Its Limitations***

Large language models trained on large corpora of source code have
demonstrated remarkable capability in generating syntactically valid
code across a wide range of programming tasks (Chen et al., 2021). The
GitHub Copilot system, based on the Codex model, was among the first
commercially deployed systems to demonstrate this capability at scale.
Subsequent evaluations have shown that while these systems produce
useful code suggestions in many cases, the rate of functionally correct
suggestions varies considerably by task complexity and domain (Austin et
al., 2021).

Perry et al. (2023) conducted a controlled study examining the security
implications of AI-assisted code generation, finding that participants
who used AI assistance were significantly more likely to introduce
security vulnerabilities than those working without assistance.
Critically, participants using AI assistance were also more confident in
the correctness of their code despite producing more vulnerable
implementations. This combination of increased error rate and increased
confidence represents the core challenge that integrity auditing tools
must address.

***Static Analysis and Code Quality Tools***

Static analysis tools analyze source code without executing it,
identifying potential defects, style violations, and security
vulnerabilities through structural examination of the code (Chess &
West, 2007). Traditional static analysis tools operate primarily at the
syntactic and type-theoretic levels. Tools such as pylint and flake8
enforce Python style guidelines and detect common programming errors.
Mypy adds optional static type checking to Python programs. Bandit
focuses specifically on security-related patterns.

Despite the breadth of existing tooling, none of these systems were
designed with AI-generated code in mind. Beller et al. (2016) noted that
static analysis tools are frequently misconfigured or ignored in
practice, in part because they generate high rates of false positives
that developers learn to dismiss. The AI Code Integrity Auditor takes a
different approach, focusing narrowly on patterns that are specifically
diagnostic of AI generation rather than general coding quality issues.

***Hallucination in Language Models***

The phenomenon of hallucination in large language models has been
studied extensively in the context of natural language generation (Ji et
al., 2023). Hallucination refers to the generation of content that is
presented with apparent confidence but is factually incorrect or
unsupported by the input. In the code generation context, this manifests
as references to nonexistent variables, calls to undefined functions,
and implementations that appear logically sound but fail to produce
correct outputs (Liu et al., 2023).

Importantly, hallucinated code is often indistinguishable from correct
code through casual inspection. The structural patterns that indicate
hallucination --- undefined name references, functions that claim to
produce output but return nothing, exception handlers that suppress all
errors --- require targeted analysis to detect reliably.

**System Design and Architecture**

***Design Philosophy***

The AI Code Integrity Auditor was designed around three core principles.
First, the tool should function as a governance layer rather than a
replacement for existing development tools. It is intended to
complement, not compete with, existing linters and type checkers by
targeting a distinct category of defect. Second, all analysis should be
reproducible and audit-friendly, with findings tied to specific file
locations and accompanied by explanations and suggested remediation
steps. Third, the tool should impose no external dependencies beyond the
Python standard library for its core analysis logic, ensuring that it
can be deployed in any Python environment without complex dependency
management.

The tool adopts a repo-root architecture in which all file paths are
resolved relative to the repository root rather than using absolute
paths. This design ensures that the tool functions correctly regardless
of where the repository is located on a given system, supporting
reproducible analysis across different development environments (Hunt &
Thomas, 1999).

***Technical Architecture***

The system is organized into four layers. The scanner layer, implemented
in *src/scanner.py*, contains all detection logic and operates as a
collection of pure functions with no side effects or file system
dependencies beyond reading the input file. The reporter layer,
implemented in *src/reporter.py*, generates structured JSON and
self-contained HTML reports from scanner output. The visualization
layer, implemented in *src/charts.py*, generates matplotlib charts
summarizing findings by severity, category, and file. The user interface
layer, implemented in *app.py*, provides a Streamlit web interface that
coordinates the other layers and presents findings to the user.

The scanner accepts files through two interfaces: a path-based interface
for use in automated pipelines and a file-object interface compatible
with Streamlit\'s file upload mechanism. This dual-interface design
allows the scanner to be used both as a standalone analysis module and
as the backend for the interactive web application.

**Detection Categories**

The AI Code Integrity Auditor implements nine categories of integrity
failure detection, seven for Python files and two for JSON files. Each
category targets a specific pattern of failure that has been identified
as characteristic of AI-generated code.

***Structural Hallucination***

Structural hallucination detection identifies Python names that are used
within a file but are never defined, imported, or available through the
Python builtin namespace. This pattern is among the most direct
indicators of AI code generation, as language models frequently generate
references to variables and functions that were not defined in the
context provided (Liu et al., 2023). The scanner builds a comprehensive
definition set by walking the abstract syntax tree (AST) of the parsed
source file, collecting all assignment targets, function and class
definitions, import statements, comprehension variables, exception
handler names, and with-statement aliases. Names used in load context
that do not appear in this definition set and are not Python builtins
are flagged as potential hallucinations.

***Silent Failure Risk***

Silent failure risk detection targets two related patterns: bare
*except* blocks that catch all exceptions including system-level
exceptions such as KeyboardInterrupt and SystemExit, and exception
handlers whose body consists entirely of a *pass* statement. Both
patterns result in exceptions being silently suppressed, preventing
error propagation and making runtime failures invisible to calling code.
Lipow (1982) identified exception handling as a primary source of
software reliability failures, and this concern is amplified in
AI-generated code where exception handlers are frequently generated as
structural boilerplate without meaningful handling logic.

***Placeholder Logic***

Placeholder logic detection identifies code elements that indicate
incomplete implementation. This includes *pass* statements in function
bodies, *raise NotImplementedError* expressions, TODO and FIXME markers
in comments, and string literals that match a curated list of
placeholder values such as \'todo\', \'temp\', \'mock\', and
\'your_api_key_here\'. AI code generators frequently produce code that
is structurally complete but contains placeholder implementations that
must be replaced before the code can function correctly. These
placeholders are often subtle and may not be apparent during casual code
review (Perry et al., 2023).

***Terminal State Failure***

Terminal state failure detection identifies functions whose names imply
that they should return a value but that contain no return statement or
contain inconsistent return paths where some branches return values and
others return None implicitly. Functions named with prefixes such as
*get\_, fetch\_, load\_, build\_, create\_,* and *parse\_* establish an
implicit contract that they will produce output. When such functions
contain no return statement, they silently return None, which typically
causes failures in calling code that expects a meaningful return value.
This pattern is particularly common in AI-generated code where function
signatures and docstrings are generated correctly but function bodies
are incomplete (Austin et al., 2021).

***Narrative State Risk***

Narrative state risk detection identifies a specific pattern in which
code announces completion or success through print statements or log
calls without performing any corresponding state-changing operation.
This pattern, described by Engler et al. (2001) as a form of belief
inconsistency in systems code, is especially prevalent in AI-generated
code because language models are trained on examples where success
messages follow successful operations. When generating new code, models
may include the success message without correctly implementing the
operation it purports to confirm. Detection operates through two passes:
an AST-level pass that identifies print calls with success-indicating
string literals, and a regex-based pass that catches broader logging
patterns.

***Control Flow Drift***

Control flow drift detection identifies unreachable code within function
bodies --- statements that appear after return, raise, break, or
continue statements in the same block. While Python does not treat
unreachable code as an error, its presence indicates logical
inconsistency in the control flow and often results from AI generation
that produces structurally redundant code (Liu et al., 2023). The
scanner walks the AST of each function, examining each statement block
for the presence of terminating statements followed by additional
statements.

***Path to Nowhere***

Path to nowhere detection identifies references to local file paths that
were not included in the uploaded file batch. When AI generates code
that references external files, it frequently invents plausible-sounding
filenames that do not correspond to files that actually exist in the
project. The scanner collects all string arguments to open() calls and
all string literals containing path separators, then checks whether the
referenced filenames appear among the uploaded files. References to
paths that do not appear in the upload batch are flagged for review.

***JSON Integrity Issues***

JSON integrity detection addresses two distinct failure modes in JSON
files. The first targets content issues: invalid JSON that fails to
parse, placeholder string values drawn from a curated list, and sample
credentials or URL patterns that indicate unfilled template values. The
second, categorized as schema drift, targets structural issues:
duplicate keys whose later values silently overwrite earlier ones during
parsing, mixed naming conventions that indicate schema inconsistency,
and high null density where more than 35% of scalar values are null,
suggesting an incompletely populated template (Pezoa et al., 2016).

**Implementation**

***AST-Based Analysis***

The primary analysis mechanism for Python files is the Python abstract
syntax tree module, which provides a structured representation of parsed
Python source code. The AST-based approach allows the scanner to reason
about the semantic structure of code rather than its textual
representation, enabling more precise detection with fewer false
positives than text-based pattern matching (Aho et al., 2006). The
scanner walks the full AST of each file to collect definitions and
usages, then applies targeted checks for each detection category.

***Token-Based Analysis***

Some detection patterns cannot be reliably identified through AST
analysis alone. Comment markers such as TODO and FIXME are stripped from
the AST during parsing and are therefore analyzed using Python\'s
tokenize module, which provides access to the token stream of the source
file before parsing. This dual-pass approach combining AST and token
analysis allows the scanner to detect a broader range of integrity
patterns than either approach could achieve independently.

***Finding Schema***

All detected issues are represented as Finding objects containing eight
fields: the filename, line number, category, severity level, message,
title, evidence (the source line that triggered the finding), and
suggestion (a recommended remediation action). The severity field takes
one of three values --- high, medium, or low --- based on the potential
impact of the detected pattern on system reliability. Structured
findings are serialized to JSON for programmatic consumption and
rendered as HTML for human review.

**User Interface and Workflow**

The application is accessed through a web browser interface built with
the Streamlit framework. Users upload Python and JSON files through a
drag-and-drop interface, and the scanner processes the uploaded files
automatically. Results are displayed in a filterable table that allows
users to narrow findings by severity, category, and filename. Three
matplotlib charts provide a visual summary of findings distribution
across severity levels, detection categories, and individual files.

Each scan session is assigned a unique identifier based on the scan
timestamp. Uploaded files are saved to a timestamped subdirectory under
*data/uploads/* and are never modified by the tool. Generated reports
are written to *output/reports/* and are available for download as
structured JSON and self-contained HTML files. This design ensures that
scan results are reproducible and that the original uploaded files are
preserved for independent review.

**Limitations and Future Work**

The AI Code Integrity Auditor employs heuristic detection methods that
are subject to both false positives and false negatives. The undefined
name detector, while comprehensive in its builtin allowlist, cannot
account for star imports, dynamic attribute creation, or names injected
through metaclasses or decorators. The narrative state risk detector
uses a fixed context window of four lines to assess whether a success
message is accompanied by a state-changing operation, which may produce
false negatives in functions where the state change occurs outside this
window.

Future work could extend the tool in several directions. Cross-file
dependency validation would allow the scanner to identify references to
functions and variables defined in other files within the same project.
Docstring-to-code consistency scoring would quantify the degree to which
function implementations match their documented behavior. Runtime
sandbox execution would allow the scanner to complement static analysis
with dynamic observation of function behavior under controlled inputs.
Integration with version control systems would enable drift detection
between AI-generated and human-written code across commit history.

**Conclusion**

The AI Code Integrity Auditor addresses a gap in existing software
development tooling by providing targeted detection of the specific
integrity failure patterns associated with AI-generated code. By
operating as a governance layer that complements rather than replaces
existing development tools, the auditor enables development teams to
incorporate AI code generation into their workflows while maintaining
systematic oversight of code quality and reliability.

As AI code generation tools become increasingly capable and widely
adopted, the need for tooling that can verify the integrity of
AI-generated outputs will only grow. The AI Code Integrity Auditor
represents an initial contribution to this emerging area, providing a
practical and extensible foundation for continued development of AI code
governance tooling.

**References**

Aho, A. V., Lam, M. S., Sethi, R., & Ullman, J. D. (2006). *Compilers:
Principles, techniques, and tools* (2nd ed.). Addison-Wesley.

Austin, J., Odena, A., Nye, M., Bosma, M., Michalewski, H., Dohan, D.,
Jiang, E., Cai, C., Terry, M., Le, Q., & Sutton, C. (2021). Program
synthesis with large language models. *arXiv preprint arXiv:2108.07732*.

Beller, M., Bholanath, R., McIntosh, S., & Zaidman, A. (2016). Analyzing
the state of static analysis: A large-scale evaluation in open source
software. In *Proceedings of the IEEE 23rd International Conference on
Software Analysis, Evolution, and Reengineering* (pp. 470--481). IEEE.

Chen, M., Tworek, J., Jun, H., Yuan, Q., Pinto, H. P. O., Kaplan, J.,
Edwards, H., Burda, Y., Joseph, N., Brockman, G., Ray, A., Puri, R.,
Krueger, G., Petrov, M., Khlaaf, H., Sastry, G., Mishkin, P., Chan, B.,
Gray, S., ... Zaremba, W. (2021). Evaluating large language models
trained on code. *arXiv preprint arXiv:2107.03374*.

Chess, B., & West, J. (2007). *Secure programming with static analysis*.
Addison-Wesley Professional.

Engler, D., Chelf, B., Chou, A., & Hallem, S. (2001). Checking system
rules using system-specific, programmer-written compiler extensions. In
*Proceedings of the 4th USENIX Symposium on Operating Systems Design and
Implementation* (pp. 1--16). USENIX Association.

Hunt, A., & Thomas, D. (1999). *The pragmatic programmer: From
journeyman to master*. Addison-Wesley.

Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang,
Y. J., Madotto, A., & Fung, P. (2023). Survey of hallucination in
natural language generation. *ACM Computing Surveys*, *55*(12), 1--38.
https://doi.org/10.1145/3571730

Lipow, M. (1982). Number of faults per line of code. *IEEE Transactions
on Software Engineering*, *SE-8*(4), 437--439.
https://doi.org/10.1109/TSE.1982.235579

Liu, J., Xia, C. S., Wang, Y., & Zhang, L. (2023). Is your code
generated by ChatGPT really correct? Rigorous evaluation of large
language models for code generation. In *Advances in Neural Information
Processing Systems 36* (pp. 1--14). Curran Associates.

Perry, N., Srivastava, M., Kumar, D., & Boneh, D. (2023). Do users write
more insecure code with AI assistants? In *Proceedings of the 2023 ACM
SIGSAC Conference on Computer and Communications Security* (pp.
2785--2799). ACM. https://doi.org/10.1145/3576915.3623157

Pezoa, F., Reutter, J. L., Suarez, F., Ugarte, M., & Vrgoč, D. (2016).
Foundations of JSON schema. In *Proceedings of the 25th International
Conference on World Wide Web* (pp. 263--273). International World Wide
Web Conferences Steering Committee.
https://doi.org/10.1145/2872427.2883029
