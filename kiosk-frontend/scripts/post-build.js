#!/usr/bin/env node
/**
 * Post-build script
 * Copies the built index.html to the correct www/ location for Frappe
 */
import { copyFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { getKioskSettings } from '../build.config.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const settings = getKioskSettings()
const { FRAPPE_APP_NAME, KIOSK_FOLDER_NAME } = settings

// Paths
const projectRoot = resolve(__dirname, '..')
const sourceHTML = resolve(projectRoot, `../${FRAPPE_APP_NAME}/public/${KIOSK_FOLDER_NAME}/index.html`)
const targetHTML = resolve(projectRoot, `../${FRAPPE_APP_NAME}/www/${KIOSK_FOLDER_NAME}.html`)

console.log('📋 Post-build: Copying HTML entry file...')
console.log(`   Source: ${sourceHTML}`)
console.log(`   Target: ${targetHTML}`)

// Check if source exists
if (!existsSync(sourceHTML)) {
  console.error(`❌ Error: Source file not found: ${sourceHTML}`)
  console.error('   Make sure vite build completed successfully.')
  process.exit(1)
}

// Copy file
try {
  copyFileSync(sourceHTML, targetHTML)
  console.log('✅ HTML entry file copied successfully!')
  console.log(`   ${KIOSK_FOLDER_NAME}.html is ready in www/`)
} catch (error) {
  console.error(`❌ Error copying file: ${error.message}`)
  process.exit(1)
}

