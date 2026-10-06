import { callApi } from './apiClient.js'
import { APP_CONFIG } from '@/config/settings.js'

const EP = APP_CONFIG.API_ENDPOINTS

export function fetchTickets(params = {}) {
  return callApi(EP.TICKETS_LIST, params)
}

export function fetchTicket(name) {
  return callApi(EP.TICKETS_DETAIL, { name })
}

export function createTicket(data) {
  return callApi(EP.TICKETS_CREATE, { data: JSON.stringify(data) }, 'POST')
}

export function updateTicket(name, data) {
  return callApi(EP.TICKETS_UPDATE, { name, data: JSON.stringify(data) }, 'POST')
}

export function addTicketAttachment(ticketName, fileName, filedataBase64) {
  return callApi(
    EP.TICKETS_ADD_ATTACHMENT,
    { ticket_name: ticketName, file_name: fileName, filedata: filedataBase64 },
    'POST',
  )
}

export function listTicketAttachments(ticketName) {
  return callApi(EP.TICKETS_LIST_ATTACHMENTS, { ticket_name: ticketName })
}

export function addTicketComment(ticketName, content) {
  return callApi(
    EP.TICKETS_ADD_COMMENT,
    { ticket_name: ticketName, content },
    'POST',
  )
}

export function listTicketComments(ticketName) {
  return callApi(EP.TICKETS_LIST_COMMENTS, { ticket_name: ticketName })
}

export function fetchTicketSummary(params = {}) {
  // Lightweight summary for dashboards (e.g. open vs waiting)
  return callApi(EP.TICKETS_LIST, params)
}



