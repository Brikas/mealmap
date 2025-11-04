# fast-python

Project Template for Python projects. Includes editor, lint, CICD, utils, and basic configurations.

-   A. There should be a separate python template for fastapi and data projects.
-   B. (selected) Downstream projects should subtract rather than build on this template.

*   [Fast Python](#fast-python)
    -   [Run](#run)
    -   [Tests](#tests)
    -   [Poetry guide](#poetry-guide)
    -   [Code quality](#code-quality)

-   Reveal file structure:
    -   `tree -a -I *.git* -I *cache* -I *node* -I *venv*`
-   Echo/cat python files and copy to clipboard:
    -   `find . -name "*.py" -type f -exec echo -e "\n\n\033[1;34m{}:\033[0m\n" \; -exec cat {} \; | xclip -selection clipboard`

## Configure

-   Configure `pyproject.toml`
-   Delete files you do not want or need. Likely this will encompass:
    -   `deploy/infra/`
