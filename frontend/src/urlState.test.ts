import { describe, expect, it } from 'vitest'

describe('timeline URL state contract', () => {
  it('round trips selected topics, channel and smoothing', () => {
    const params = new URLSearchParams()
    params.set('topics', 'climate_change,clean_transport')
    params.set('channel', 'bluesky')
    params.set('smooth', '0')
    params.set('plot', 'layers')
    params.set('layers', 'news,social')
    expect(params.get('topics')?.split(',')).toEqual(['climate_change', 'clean_transport'])
    expect(params.get('channel')).toBe('bluesky')
    expect(params.get('smooth')).toBe('0')
    expect(params.get('plot')).toBe('layers')
    expect(params.get('layers')?.split(',')).toEqual(['news', 'social'])
  })
})
