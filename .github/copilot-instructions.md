# Copilot Instructions for AI Coding Agents

## Project Overview
This is a Django-based web application with a modular structure. The main components are:
- `iq/`, `learners/`, `pricing/`, `superadmin/`, `users/`, `website/`: Django apps, each with their own models, views, templates, migrations, and admin configuration.
- `main/`: Contains global Django settings and entry points (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).
- `media/` and `static/`: Store user-uploaded files and static assets, respectively.
- `templates/`: Shared base templates and email templates.

## Key Workflows
- **Run the server:**
  ```powershell
  python manage.py runserver
  ```
- **Apply migrations:**
  ```powershell
  python manage.py migrate
  ```
- **Create migrations:**
  ```powershell
  python manage.py makemigrations
  ```
- **Run tests:**
  ```powershell
  python manage.py test
  ```
- **Static files:**
  Collect static files with:
  ```powershell
  python manage.py collectstatic
  ```

## Patterns & Conventions
- Each app follows Django conventions: models, views, admin, migrations, templates.
- Shared templates are in `templates/`, app-specific templates are in `app/templates/app/`.
- Media files are organized by type and user/email in `media/`.
- Static assets are in `static/`, with subfolders for CSS, JS, fonts, images, and vendor files.
- Management commands are in `app/management/commands/`.
- Use relative imports within apps, absolute imports for cross-app references.
- Database is SQLite by default (`db.sqlite3`).

## Integration Points
- External dependencies are listed in `requirements.txt`.
- Email templates are in `templates/emails/`.
- Custom storage backends and email backends are in `users/storage_backends.py` and `users/email_backends.py`.

## Examples
- To add a new model, create it in `app/models.py`, run `makemigrations`, then `migrate`.
- To add a view, update `app/views.py` and `app/urls.py`, then add templates in `app/templates/app/`.
- For custom management commands, add Python files to `app/management/commands/`.

## Tips for AI Agents
- Always check for app-specific templates before using shared ones.
- When editing models, update migrations and run tests.
- Use Django admin for quick data inspection (`python manage.py createsuperuser` to create an admin user).
- Reference `main/settings.py` for configuration details (databases, static/media paths, installed apps).

---
_If any section is unclear or missing important project-specific details, please provide feedback to improve these instructions._
