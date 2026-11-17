import { describe, it, expect } from 'vitest'
import { emptyServer, metadataError, withServerType } from './contractMetadata'

describe('withServerType', () => {
  it('clears keys the new type does not take and keeps shared ones', () => {
    const server = { ...emptyServer(), server: 'prod', host: 'h', catalog: 'c', schema_name: 's' }
    expect(withServerType(server, 'azure')).toMatchObject({ type: 'azure', server: 'prod', host: '', catalog: '', schema_name: '' })
    expect(withServerType(server, 'postgres')).toMatchObject({ host: 'h', schema_name: 's', catalog: '' })
    expect(withServerType({ ...server, type: 'postgres', port: 5432 }, 'local').port).toBeNull()
  })
})

describe('metadataError', () => {
  it('is null when every row is complete or absent, and names the first incomplete row', () => {
    expect(metadataError([], [], [])).toBeNull()
    expect(metadataError([{ username: '', name: 'x', role: '' }], [], [])).toBe('Team member 1 needs a username')
    expect(metadataError([], [{ channel: ' ', url: '', tool: '', scope: '' }], [])).toBe('Support channel 1 needs a channel')
    expect(metadataError([], [], [emptyServer()])).toBe('Server 1 needs a name')
    expect(metadataError([], [], [{ ...emptyServer(), server: 'a', type: 'postgres', host: 'h' }]))
      .toBe('Server 1 (postgres) needs Port, Database, Schema')
  })
})


import { safeUrl, serverLocation } from './contractMetadata'

describe('safeUrl', () => {
  it.each(['https://example.com', 'http://example.com', 'mailto:a@example.com', 'HTTPS://example.com'])(
    'keeps %s', (url) => expect(safeUrl(url)).toBe(url),
  )
  it.each(['javascript:alert(1)', ' javascript:alert(1)', 'data:text/html,x', ''])(
    'refuses %j', (url) => expect(safeUrl(url)).toBeNull(),
  )
})

describe('serverLocation', () => {
  it('formats each type', () => {
    const base = emptyServer()
    expect(serverLocation({ ...base, host: 'h', catalog: 'c', schema_name: 's' })).toBe('h / c.s')
    expect(serverLocation({ ...base, catalog: 'c', schema_name: 's' })).toBe('c.s')
    expect(serverLocation({ ...base, type: 'postgres', host: 'h', port: 5432, database: 'd', schema_name: 's' })).toBe('h:5432/d.s')
    expect(serverLocation({ ...base, type: 'azure', location: 'az://a/b', format: 'csv' })).toBe('az://a/b (csv)')
    expect(serverLocation({ ...base, type: 'local', path: './a.csv', format: 'csv' })).toBe('./a.csv (csv)')
  })
})
