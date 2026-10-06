// Regenerate the Frappe www shell from the built index.html so hashed asset
// filenames always match. Injects the Jinja boot block (csrf token, user)
// that www/amazonus.py provides.
import { readFileSync, writeFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const here = path.dirname(fileURLToPath(import.meta.url))
const built = path.resolve(here, '../../khanal_tech_integrations/public/amazonus/index.html')
const shell = path.resolve(here, '../../khanal_tech_integrations/www/amazonus.html')

const bootBlock = `
    <script>
      {% for key in boot %}
      window["{{ key }}"] = {{ boot[key] | tojson }};
      {% endfor %}
    </script>
`

let html = readFileSync(built, 'utf8')
html = html.replace('</body>', `${bootBlock}\n  </body>`)
writeFileSync(shell, html)
console.log('www/amazonus.html regenerated from build output')
