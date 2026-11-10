#!/usr/bin/env python3
"""Render non-secret tenant bindings into offline Base workflow draft bodies."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import UUID

PARAMS = {'table_name', 'project_key', 'owner_key', 'linear_team_id',
          'linear_assignee_id', 'todo_state_id', 'done_state_id',
          'canceled_state_id', 'parent_url_prefix', 'fields'}
FIELDS = {'source_key', 'title', 'node_name', 'linear_id', 'create_attempted',
          'source_task_id', 'state', 'parent_name', 'parent_id'}
class ConfigError(ValueError):
    pass


TOKEN = re.compile(r'\{\{([a-z_.]+)\}\}')


def validate(config):
    if not isinstance(config, dict) or set(config) != PARAMS:
        raise ConfigError('config must contain exactly the documented non-secret parameter keys')
    for key in PARAMS - {'fields'}:
        value = config[key]
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ConfigError(f'{key}: expected nonempty text without surrounding whitespace')
        if 'SET_ME' in value or '{{' in value or 'YOUR_' in value:
            raise ConfigError(f'{key}: unresolved configuration value')
        if re.search(r'lin_api_|Bearer\s|[\r\n]', value, re.I):
            raise ConfigError(f'{key}: credentials and line breaks are not accepted')
    for key in ('project_key', 'owner_key'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', config[key]):
            raise ConfigError(f'{key}: expected a source key, not a name, URL or credential')
    for key in ('linear_team_id', 'linear_assignee_id', 'todo_state_id', 'done_state_id', 'canceled_state_id'):
        try:
            parsed = UUID(config[key])
            if not parsed.int or str(parsed) != config[key].lower():
                raise ConfigError()
        except (ValueError, AttributeError):
            raise ConfigError(f'{key}: expected a canonical nonzero UUID') from None
    if len({config[k] for k in ('todo_state_id', 'done_state_id', 'canceled_state_id')}) != 3:
        raise ConfigError('Todo, Done and Canceled require distinct state IDs')
    url = urlsplit(config['parent_url_prefix'])
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or not url.path.endswith('/')
            or re.search(r'[\s"<>\\]', config['parent_url_prefix'])):
        raise ConfigError('parent_url_prefix: expected a credential-free HTTPS prefix ending in /')
    fields = config['fields']
    if not isinstance(fields, dict) or set(fields) != FIELDS:
        raise ConfigError('fields must contain exactly the nine documented field aliases')
    if any(not isinstance(v, str) or not re.fullmatch(r'fld[A-Za-z0-9]+', v) for v in fields.values()):
        raise ConfigError('fields: expected real Base field IDs beginning with fld')
    if len(set(fields.values())) != len(fields):
        raise ConfigError('fields: each alias must refer to a distinct field ID')


def render(value, config):
    if isinstance(value, dict):
        return {k: render(v, config) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, config) for v in value]
    if isinstance(value, str):
        def replace(match):
            name = match[1]
            return config['fields'][name[7:]] if name.startswith('fields.') else config[name]
        return TOKEN.sub(replace, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        validate(config)
        template = json.loads((Path(__file__).resolve().parents[1] / 'assets/task-workflows.template.json').read_text())
        bodies = render(template, config)
        serialized = {name: json.dumps(body, ensure_ascii=False, indent=2) + '\n' for name, body in bodies.items()}
        if any('{{' in s for s in serialized.values()):
            raise ConfigError('template contains unresolved parameter markers')
        for body in bodies.values():
            ids = [node['id'] for node in body['steps']]
            if len(ids) != len(set(ids)):
                raise ConfigError('template has duplicate node IDs')
            for node in body['steps']:
                links = [node.get('next')] + [edge['to'] for edge in node.get('children', {}).get('links', [])]
                if any(target and target not in ids for target in links):
                    raise ConfigError('template has an invalid graph link')
        if args.out.exists():
            raise ConfigError('output directory already exists; choose a new directory')
        args.out.mkdir(parents=True, exist_ok=False)
        for name, content in serialized.items():
            (args.out / f'{name}.json').write_text(content)
        print(json.dumps({'status': 'needs_credentials_and_live_validation',
                          'files': [f'{name}.json' for name in serialized]}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Never echo config values or an exception that may contain a credential.
        message = str(exc) if isinstance(exc, ConfigError) else type(exc).__name__
        print(f'render failed: {message}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
