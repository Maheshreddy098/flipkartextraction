#!/usr/bin/env node
import { copyFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { getSettings } from '../build.config.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const settings = getSettings()
const { FRAPPE_APP_NAME, FOLDER_NAME } = settings

const projectRoot = resolve(__dirname, '..')
const sourceHTML = resolve(projectRoot, `../${FRAPPE_APP_NAME}/public/${FOLDER_NAME}/index.html`)
const targetHTML = resolve(projectRoot, `../${FRAPPE_APP_NAME}/www/${FOLDER_NAME}.html`)

console.log('Post-build: Copying HTML entry file...')
console.log(`  Source: ${sourceHTML}`)
console.log(`  Target: ${targetHTML}`)

if (!existsSync(sourceHTML)) {
  console.error(`Error: Source file not found: ${sourceHTML}`)
  process.exit(1)
}

try {
  copyFileSync(sourceHTML, targetHTML)
  console.log(`Done! ${FOLDER_NAME}.html is ready in www/`)
} catch (error) {
  console.error(`Error copying file: ${error.message}`)
  process.exit(1)
}
