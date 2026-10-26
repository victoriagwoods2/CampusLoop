import { FormEvent, useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
type User = { id: string; email: string; display_name: string; is_demo: boolean }
type Listing = { id: string; user_id: string; item_name: string; description: string; category: string; quantity: number; remaining_quantity: number; condition: string; defects: string; area: string; available_from: string; pickup_deadline: string; pickup_windows: string; time_from: string; time_until: string; requires_vehicle: boolean; can_deliver: boolean; dimensions: string; public_status: string; status: string; is_demo: boolean; display_name: string }
type Need = { id: string; user_id: string; item_name: string; category: string; quantity: number; arrival_date: string; available_from: string; available_until: string; time_from: string; time_until: string; area: string; has_vehicle: boolean; preferred_condition: string; essential_category: string; requires_delivery: boolean; is_demo: boolean }
type Reservation = { id: string; listing_id: string; recipient_id: string; item_name: string; area: string; quantity: number; status: string; transport_plan: string; pickup_window: string; pickup_agreed: boolean; listing_from: string; listing_until: string; listing_pickup_windows: string; listing_time_from: string; listing_time_until: string; giver_confirmed: boolean; recipient_confirmed: boolean; is_giver: boolean; giver_name: string; recipient_name: string }
type Resource = { id: string; name: string; url: string; category: string; accepted_items: string[]; notes: string; acceptance_verified: boolean; location: string }
type Plan = { id: string; direction?: string; status: string; matches: { listing_id: string; need_id: string; quantity: number; why: string; next_action: string; issues: string[]; listing?: {item_name:string;category:string;area:string;is_demo:boolean}; need?: {item_name:string;area:string;is_demo:boolean}; same_giver_group_size?:number }[]; possible_matches?: { listing_id: string; need_id: string; issue: string; next_action: string }[]; unmatched: { listing_id?: string; need_id?: string; item_name: string; reason: string }[]; resources: { resource_id: string; name: string; url: string; item: string; why: string; acceptance_verified: boolean; next_action: string }[]; missing_info: string[]; usage?: { model: string; requests: { input_tokens: number | null; cached_input_tokens: number | null; output_tokens: number | null }[]; cost_usd: number | null; pricing_status: string }; action_summary?: string }
type Usage = { model: string; requests: { model: string; input_tokens: number | null; cached_input_tokens: number | null; output_tokens: number | null; latency_ms: number | null; tool_calls: number; tool_names?: string[]; status: string; created_at: string }[]; pricing_status: string; costs: Record<string, number | null>; scenario_assumption_runs_per_user_month: number }
type Tab = 'home' | 'browse' | 'out' | 'in' | 'handoffs' | 'donate' | 'evidence'

function pickupLabel(value: string) {
  const match = /^(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?$/.exec(value.trim())
  if (!match) return value || 'No requested pickup time saved'
  return `${dateLabel(match[1])}${match[2] ? ` at ${match[2]} (New Haven local time)` : ''}`
}

function listingWindowLabel(reservation: Reservation) {
  const dates = `${dateLabel(reservation.listing_from)} – ${dateLabel(reservation.listing_until)}`
  const times = reservation.listing_time_from && reservation.listing_time_until
    ? `${reservation.listing_time_from}–${reservation.listing_time_until} (New Haven local time)`
    : reservation.listing_pickup_windows
  return `${dates}${times ? ` · ${times}` : ''}`
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('campusloop-token')
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
  return data as T
}

function isoOffset(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
function dateLabel(value: string) {
  if (!value) return 'Date not set'
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}
function initials(name: string) { return name.split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') }

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('campusloop-token'))
  const [user, setUser] = useState<User | null>(null)
  const [tab, setTab] = useState<Tab>('home')
  const [listings, setListings] = useState<Listing[]>([])
  const [ownListings, setOwnListings] = useState<Listing[]>([])
  const [needs, setNeeds] = useState<Need[]>([])
  const [ownNeeds, setOwnNeeds] = useState<Need[]>([])
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [usage, setUsage] = useState<Usage | null>(null)
  const [health, setHealth] = useState<{ ai_configured: boolean; ai_model: string; ai_status: string } | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All items')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [planBusy, setPlanBusy] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planScope, setPlanScope] = useState<{ userId: string; direction: 'move_out' | 'move_in'; listingIds: string[]; needIds: string[]; fingerprint: string } | null>(null)
  const [selectedListingIds, setSelectedListingIds] = useState<string[]>([])
  const [selectedNeedIds, setSelectedNeedIds] = useState<string[]>([])
  const [listingFormOpen, setListingFormOpen] = useState(false)
  const [needFormOpen, setNeedFormOpen] = useState(false)
  const [handoffFilter, setHandoffFilter] = useState<'requested' | 'reserved' | 'completed'>('requested')
  const [requestListing, setRequestListing] = useState<Listing | null>(null)
  const [editingListing, setEditingListing] = useState<Listing | null>(null)
  const [editingNeed, setEditingNeed] = useState<Need | null>(null)
  const [authError, setAuthError] = useState('')
  const [registering, setRegistering] = useState(false)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    if (!localStorage.getItem('campusloop-token')) return
    setLoading(true)
    try {
      const [market, mine, openNeeds, personalNeeds, handoffs, sources, metrics] = await Promise.all([
        api<Listing[]>('/api/listings'), api<Listing[]>('/api/listings?mine=true'), api<Need[]>('/api/needs'), api<Need[]>('/api/needs?mine=true'), api<Reservation[]>('/api/reservations'), api<Resource[]>('/api/resources'), api<Usage>('/api/usage'),
      ])
      setListings(market); setOwnListings(mine); setNeeds(openNeeds); setOwnNeeds(personalNeeds); setReservations(handoffs); setResources(sources); setUsage(metrics)
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }

  useEffect(() => { api<typeof health>('/api/health').then(setHealth).catch(() => setHealth(null)) }, [])
  useEffect(() => { setNotice(''); setError('') }, [tab])
  useEffect(() => {
    if (!token) return
    api<User>('/api/auth/me').then(value => { setUser(value); refresh() }).catch(() => { localStorage.removeItem('campusloop-token'); setToken(null); setUser(null) })
  }, [token])

  async function run(action: () => Promise<unknown>, success?: string) {
    setBusy(true); setError(''); setNotice('')
    try { await action(); setPlan(null); setPlanScope(null); if (success) setNotice(success); await refresh() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  async function signIn(email: string, password: string, form?: FormEvent) {
    form?.preventDefault(); setAuthError('')
    try {
      const result = await api<{ token: string; user: User }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      localStorage.setItem('campusloop-token', result.token); setPlan(null); setPlanScope(null); setSelectedListingIds([]); setSelectedNeedIds([]); setTab('home'); setToken(result.token); setUser(result.user); await refresh()
    } catch (e) { setAuthError((e as Error).message) }
  }
  async function signOut() {
    await api('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
    localStorage.removeItem('campusloop-token'); setPlan(null); setPlanScope(null); setSelectedListingIds([]); setSelectedNeedIds([]); setTab('home'); setToken(null); setUser(null); setListings([]); setOwnListings([]); setOwnNeeds([]); setNeeds([]); setReservations([])
  }

  async function createListing(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const f = new FormData(form)
    const payload = { item_name: f.get('item_name'), description: f.get('description'), category: f.get('category'), quantity: Number(f.get('quantity')), condition: f.get('condition'), defects: f.get('defects'), area: f.get('area'), available_from: f.get('available_from'), pickup_deadline: f.get('pickup_deadline'), pickup_windows: f.get('pickup_windows'), time_from: f.get('time_from'), time_until: f.get('time_until'), requires_vehicle: f.get('requires_vehicle') === 'on', can_deliver: f.get('can_deliver') === 'on', dimensions: f.get('dimensions') }
    await run(async () => { await api(`/api/listings${editingListing ? `/${editingListing.id}` : ''}`, { method: editingListing ? 'PATCH' : 'POST', body: JSON.stringify(payload) }); setEditingListing(null); setListingFormOpen(false); form.reset() }, editingListing ? 'Listing updated.' : 'Your listing is live.')
  }
  async function createNeed(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const f = new FormData(form)
    const payload = { item_name: f.get('item_name'), category: f.get('category'), quantity: Number(f.get('quantity')), arrival_date: f.get('arrival_date'), available_from: f.get('available_from'), available_until: f.get('available_until'), time_from: f.get('time_from'), time_until: f.get('time_until'), area: f.get('area'), has_vehicle: f.get('has_vehicle') === 'on', preferred_condition: f.get('preferred_condition'), essential_category: f.get('essential_category'), requires_delivery: f.get('requires_delivery') === 'on' }
    await run(async () => { await api(`/api/needs${editingNeed ? `/${editingNeed.id}` : ''}`, { method: editingNeed ? 'PATCH' : 'POST', body: JSON.stringify(payload) }); setEditingNeed(null); setNeedFormOpen(false); form.reset() }, editingNeed ? 'Request updated.' : 'Your need is posted.')
  }
  async function createPlan(direction: 'move_out' | 'move_in') {
    if (planBusy) return
    const listingIds = direction === 'move_out' ? [...selectedListingIds] : []
    const needIds = direction === 'move_in' ? [...selectedNeedIds] : []
    const snapshot = direction === 'move_out'
      ? listingIds.map(id => ownListings.find(row => row.id === id)).filter(Boolean)
      : needIds.map(id => ownNeeds.find(row => row.id === id)).filter(Boolean)
    setPlanBusy(true); setError(''); setNotice(''); setPlan(null); setPlanScope(null)
    try {
      const result = await api<Plan>('/api/plans', { method: 'POST', body: JSON.stringify({ direction, listing_ids: listingIds, need_ids: needIds }) })
      setPlan(result); setPlanScope({ userId: user!.id, direction, listingIds, needIds, fingerprint: JSON.stringify(snapshot) }); setNotice('Your plan is ready. Review each proposed handoff before taking action.'); await refresh()
    } catch (e) { setError((e as Error).message) }
    finally { setPlanBusy(false) }
  }
  async function submitReservation(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!requestListing) return
    const f = new FormData(e.currentTarget); const needId = String(f.get('need_id') || '')
    const date = String(f.get('pickup_date') || '')
    const time = String(f.get('pickup_time') || '')
    const need = ownNeeds.find(n => n.id === needId)
    const transport = (need?.requires_delivery || (requestListing.requires_vehicle && !need?.has_vehicle)) ? 'delivery requested' : requestListing.requires_vehicle ? 'recipient vehicle' : 'easy to carry'
    await run(async () => { await api('/api/reservations', { method: 'POST', body: JSON.stringify({ listing_id: requestListing.id, need_id: needId || null, quantity: Number(f.get('quantity')), transport_plan: transport, pickup_window: `${date}${time ? ` ${time}` : ''}` }) }); setRequestListing(null) }, 'Request sent to the giver. It is not reserved until they accept.')
  }
  async function decision(id: string, action: 'accept' | 'decline', agreedPickup = '') {
    const message = action === 'decline'
      ? 'Request declined; the quantity is available again.'
      : agreedPickup
        ? `Request accepted. You agreed to ${pickupLabel(agreedPickup)}.`
        : 'Request accepted. No pickup appointment was saved; the listing availability is shown below.'
    await run(() => api(`/api/reservations/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision: action, ...(agreedPickup ? { pickup_window: agreedPickup } : {}) }) }), message)
  }
  async function confirmHandoff(id: string) {
    const confirmation = user?.id === reservations.find(row => row.id === id)?.recipient_id
      ? 'You confirmed that you have received the item. This records a completed physical exchange, not a future pickup.'
      : 'You confirmed that you have handed over the item. This records a completed physical exchange, not a future pickup.'
    await run(() => api(`/api/reservations/${id}/confirm`, { method: 'POST', body: JSON.stringify({ completed: true }) }), confirmation)
  }
  async function resetDemo() {
    if (!window.confirm('Restore the fictional demonstration records? Real listings, requests, and reservations are kept.')) return
    setPlan(null); await run(() => api('/api/demo/reset', { method: 'POST' }), 'Demonstration data restored.')
  }

  const visibleListings = useMemo(() => listings.filter(item => {
    const q = query.toLowerCase().trim()
    return (category === 'All items' || item.category === category) && (!q || `${item.item_name} ${item.description} ${item.area}`.toLowerCase().includes(q))
  }), [listings, query, category])
  const categories = useMemo(() => ['All items', ...new Set(listings.map(item => item.category))], [listings])
  const scopedRecords = planScope?.direction === 'move_out'
    ? planScope.listingIds.map(id => ownListings.find(row => row.id === id)).filter(Boolean)
    : planScope?.needIds.map(id => ownNeeds.find(row => row.id === id)).filter(Boolean)
  const currentSelectedIds = planScope?.direction === 'move_out' ? selectedListingIds : selectedNeedIds
  const selectedScopeIsCurrent = Boolean(planScope && JSON.stringify([...currentSelectedIds].sort()) === JSON.stringify([...(planScope.direction === 'move_out' ? planScope.listingIds : planScope.needIds)].sort()))
  const planIsCurrent = Boolean(plan && planScope && user?.id === planScope.userId && plan.direction === planScope.direction && tab === (planScope.direction === 'move_out' ? 'out' : 'in') && selectedScopeIsCurrent && JSON.stringify(scopedRecords) === planScope.fingerprint)
  const handoffsToShow = reservations.filter(row => row.status === handoffFilter)

  if (!user) return <Login onLogin={signIn} error={authError} registering={registering} setRegistering={setRegistering} />

  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => setTab('home')} aria-label="CampusLoop home"><span className="brand-mark">↗</span><span>campusloop<small>pass it forward</small></span></button>
      <nav className="desktop-nav" aria-label="Main navigation">
        {([['home','Home'], ['browse', 'Find items'], ['out', 'Moving out'], ['in', 'Moving in'], ['handoffs', 'Handoffs'], ['donate', 'Donation guide']] as [Tab,string][]).map(([key,label]) => <button key={key} className={tab === key ? 'nav-link active' : 'nav-link'} onClick={() => setTab(key)}>{label}</button>)}
      </nav>
      <button className={tab === 'evidence' ? 'nav-link evidence-link active' : 'nav-link evidence-link'} onClick={() => setTab('evidence')}>Project evidence</button>
      <div className="account-menu"><span className="avatar">{initials(user.display_name)}</span><span className="account-name">{user.display_name}<small>{user.is_demo ? 'Demonstration account' : 'Local account'}</small></span><button className="signout" onClick={signOut}>Sign out</button></div>
    </header>

    {(notice || error) && <div className={error ? 'toast error-toast' : 'toast success-toast'} role="status"><span>{error ? '!' : '✓'}</span><div>{error || notice}</div><button onClick={() => { setError(''); setNotice('') }} aria-label="Dismiss">×</button></div>}

    {!health?.ai_configured && <div className="ai-banner"><span className="pulse-dot"/><span><strong>AI planning is paused.</strong> Add <code>PORTKEY_API_KEY</code> to <code>final project/.env</code> or the parent folder’s <code>.env</code>. Listings and handoffs still work.</span></div>}
    <main>
      {tab === 'home' && <><section className="welcome-row"><div><p className="eyebrow">NEW HAVEN · STUDENT TO STUDENT</p><h1>A softer landing,<br /><em>on both sides</em> of move day.</h1><p className="welcome-copy">Find a next home for useful things. Find the essentials you need. Make the handoff work for both people.</p></div><div className="hero-note"><span className="note-icon">✳</span><p>Every listing here is free.<br /><strong>Good things keep going.</strong></p><span className="note-scribble">↘</span></div></section>
      <section className="entry-cards" aria-label="Get started">
        <button className="entry-card out-card" onClick={() => setTab('out')}><span className="entry-number">01 / GIVE</span><span className="entry-icon">↗</span><strong>I’m moving out</strong><span>List what you can pass along</span><span className="arrow">↗</span></button>
        <button className="entry-card in-card" onClick={() => setTab('in')}><span className="entry-number">02 / FIND</span><span className="entry-icon">⌕</span><strong>I’m moving in</strong><span>Find useful secondhand essentials</span><span className="arrow">↗</span></button>
        <div className="entry-aside"><span className="tiny-star">✳</span><strong>A little more circular.<br />A little less stressful.</strong><span>Free items · clear pickup windows · no exact addresses</span></div>
      </section></>}

      {tab !== 'home' && <div className="section-heading"><div><p className="eyebrow">{tab === 'browse' ? 'THE EXCHANGE' : tab === 'out' ? 'PASS IT ALONG' : tab === 'in' ? 'MAKE A WISH LIST' : tab === 'handoffs' ? 'REQUESTS · RESERVATIONS · PICKUPS' : tab === 'donate' ? 'LOCAL OPTIONS' : 'THE PROJECT, IN PRACTICE'}</p><h1>{tab === 'browse' ? 'Find items' : tab === 'out' ? 'Your listings' : tab === 'in' ? 'Your requests' : tab === 'handoffs' ? 'Handoffs' : tab === 'donate' ? 'Donation resources' : 'Project evidence'}</h1></div><span className="section-counter">{tab === 'browse' ? <><b>{visibleListings.length}</b> <i>{visibleListings.length === 1 ? 'item available' : 'items available'}</i></> : tab === 'out' ? <><b>{ownListings.length}</b> <i>{ownListings.length === 1 ? 'listing' : 'listings'}</i></> : tab === 'in' ? <><b>{ownNeeds.length}</b> <i>{ownNeeds.length === 1 ? 'request' : 'requests'}</i></> : tab === 'handoffs' ? <><b>{reservations.filter(r => r.status === 'requested').length}</b> <i>pending · {reservations.filter(r => r.status === 'reserved').length} reserved · {reservations.filter(r => r.status === 'completed').length} completed</i></> : tab === 'donate' ? <><b>{resources.length}</b> <i>local resources</i></> : <><b>{usage?.requests.filter(r => r.status === 'success').length || 0}</b> <i>successful AI calls</i></>}</span></div>}

      {tab === 'browse' && <section className="browse-layout">
        <aside className="filter-panel"><div className="panel-title"><span>⌕</span><strong>Find your thing</strong></div><label className="field-label" htmlFor="search-items">Search items</label><input id="search-items" placeholder="Try cookware, lamp…" value={query} onChange={e => setQuery(e.target.value)} /><label className="field-label" htmlFor="category-filter">Category</label><select id="category-filter" value={category} onChange={e => setCategory(e.target.value)}>{categories.map(x => <option key={x}>{x}</option>)}</select><div className="filter-hint"><span>↗</span><p>Know your dates and how you’ll carry it? Check both before you request.</p></div><button className="text-button" onClick={() => setTab('in')}>Post a request instead <b>→</b></button></aside>
        <div className="listing-area"><div className="result-line"><span>{loading ? 'Loading listings…' : `${visibleListings.length} ${visibleListings.length === 1 ? 'item' : 'items'} to explore`}</span><span>All items are free <b>·</b> General pickup areas only</span></div>
          {visibleListings.length ? <div className="listing-grid">{visibleListings.map((item, i) => <ListingCard key={item.id} item={item} index={i} onRequest={() => setRequestListing(item)} />)}</div> : <EmptyState icon="⌕" title="Nothing here yet" text={query ? 'Try a different search or category.' : 'New things appear as students make their plans.'} />}
        </div>
      </section>}

      {tab === 'out' && <section className="record-layout"><div className="owned-panel records-panel"><div className="records-heading"><div><p className="eyebrow">PASS IT ALONG</p><h2>My listings</h2></div><button className="button-primary" onClick={() => { setEditingListing(null); setListingFormOpen(true); setTimeout(() => document.querySelector('.form-panel')?.scrollIntoView({behavior:'smooth'}), 0) }}>Add an item <span>＋</span></button></div><p className="muted">Keep track of what is available and select listings to plan a next home.</p>
        {ownListings.length ? <>{ownListings.map(item => <div className="owned-row" key={item.id}><input aria-label={`Include ${item.item_name} in plan`} type="checkbox" checked={selectedListingIds.includes(item.id)} onChange={e => setSelectedListingIds(e.target.checked ? [...selectedListingIds,item.id] : selectedListingIds.filter(id=>id!==item.id))} /><div className="owned-copy"><strong>{item.item_name}</strong><span>{item.remaining_quantity} available · until {dateLabel(item.pickup_deadline)}</span></div><StatusPill status={item.public_status} /><button className="icon-button" title="Edit listing" disabled={Boolean(reservations.some(r => r.listing_id===item.id && ['requested','reserved'].includes(r.status)))} onClick={() => { setEditingListing(item); setListingFormOpen(true); setTimeout(() => document.querySelector('.form-panel')?.scrollIntoView({behavior:'smooth'}), 0) }}>✎</button><button className="icon-button" title="Withdraw listing" disabled={item.status==='withdrawn'} onClick={() => run(() => api(`/api/listings/${item.id}/withdraw`, { method:'POST' }), 'Listing withdrawn.')}>×</button></div>)}<button className="button-secondary full-width" disabled={!selectedListingIds.length || planBusy || !health?.ai_configured} onClick={() => createPlan('move_out')}>{planBusy ? 'Building a plan…' : 'Find matches for my listings'}<small>{selectedListingIds.length ? `${selectedListingIds.length} selected` : 'Select listings above'}</small></button></> : <EmptyState icon="↗" title="No listings yet" text="Add an item to make it available." />}
      </div>{listingFormOpen && <div className="form-panel"><div className="form-title-row"><div><p className="eyebrow">GIVE A GOOD THING ANOTHER LIFE</p><h2>{editingListing ? 'Edit listing' : 'Add an item'}</h2></div><button className="button-quiet" type="button" onClick={() => { setListingFormOpen(false); setEditingListing(null) }}>Close</button></div><form key={editingListing?.id||'new-listing'} onSubmit={createListing} className="form-grid">
        <label className="wide">Item name<input name="item_name" required maxLength={100} defaultValue={editingListing?.item_name} placeholder="e.g. kettle, floor lamp" /></label>
        <label>Category<select name="category" required defaultValue={editingListing?.category || 'Household'}>{['Household','Kitchen','Lighting','Furniture','Books','Clothing','Other'].map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Quantity<input name="quantity" type="number" min="1" max="100" required defaultValue={editingListing?.quantity ?? 1} /></label>
        <label>Condition<select name="condition" defaultValue={editingListing?.condition || 'Good'}>{['New','Like new','Good','Fair','Poor'].map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Pickup area<input name="area" required maxLength={80} defaultValue={editingListing?.area} placeholder="e.g. East Rock" /></label>
        <label>Available from<input name="available_from" type="date" required defaultValue={editingListing?.available_from || isoOffset(1)} /></label>
        <label>Pickup deadline<input name="pickup_deadline" type="date" required defaultValue={editingListing?.pickup_deadline || isoOffset(7)} /></label>
        <details className="wide more-details" open={Boolean(editingListing)}><summary>More details</summary><div className="form-grid"><label className="wide">Pickup time windows<input name="pickup_windows" maxLength={160} defaultValue={editingListing?.pickup_windows} placeholder="e.g. weekday afternoons" /></label><label>Window starts (local)<input name="time_from" type="time" defaultValue={editingListing?.time_from||''} /></label><label>Window ends (local)<input name="time_until" type="time" defaultValue={editingListing?.time_until||''} /></label><label className="wide">Description<textarea name="description" maxLength={600} defaultValue={editingListing?.description} placeholder="What should the next person know?" rows={3} /></label><label className="wide">Defects or wear<input name="defects" maxLength={240} defaultValue={editingListing?.defects} placeholder="Mention anything they should know" /></label><label className="wide">Dimensions<input name="dimensions" maxLength={120} defaultValue={editingListing?.dimensions} placeholder="e.g. 20 × 14 × 10 in" /></label><label className="check-row wide"><input type="checkbox" name="requires_vehicle" defaultChecked={editingListing?.requires_vehicle} /><span>Needs a vehicle or substantial lifting</span></label><label className="check-row wide"><input type="checkbox" name="can_deliver" defaultChecked={editingListing?.can_deliver} /><span>I may be able to deliver; we still need to agree</span></label></div></details>
        <div className="wide form-actions"><button className="button-primary" disabled={busy}>{busy ? 'Saving…' : editingListing ? 'Save changes' : 'Post item'} <span>↗</span></button>{editingListing && <button type="button" className="button-quiet" onClick={() => { setEditingListing(null); setListingFormOpen(false) }}>Cancel edit</button>}<span className="form-footnote">No exact address or phone number is shown.</span></div>
      </form></div>}</section>}

      {tab === 'in' && <section className="record-layout"><div className="owned-panel records-panel"><div className="records-heading"><div><p className="eyebrow">MAKE A WISH LIST</p><h2>My requests</h2></div><button className="button-primary" onClick={() => { setEditingNeed(null); setNeedFormOpen(true); setTimeout(() => document.querySelector('.form-panel')?.scrollIntoView({behavior:'smooth'}), 0) }}>Add a request <span>＋</span></button></div><p className="muted">Select a request to find available items that may fit.</p>
        {ownNeeds.length ? <>{ownNeeds.map(need => <div className="owned-row" key={need.id}><input type="checkbox" aria-label={`Include ${need.item_name} in plan`} checked={selectedNeedIds.includes(need.id)} onChange={e => setSelectedNeedIds(e.target.checked ? [...selectedNeedIds,need.id] : selectedNeedIds.filter(id=>id!==need.id))} /><div className="owned-copy"><strong>{need.item_name} <small>× {need.quantity}</small></strong><span>Available {dateLabel(need.available_from)} – {dateLabel(need.available_until)}</span></div><button className="icon-button" title="Edit request" onClick={() => { setEditingNeed(need); setNeedFormOpen(true); setTimeout(() => document.querySelector('.form-panel')?.scrollIntoView({behavior:'smooth'}), 0) }}>✎</button></div>)}<button className="button-secondary full-width" disabled={!selectedNeedIds.length || planBusy || !health?.ai_configured} onClick={() => createPlan('move_in')}>{planBusy ? 'Finding matches…' : 'Find items for my requests'}<small>{selectedNeedIds.length ? `${selectedNeedIds.length} selected` : 'Select requests above'}</small></button></> : <EmptyState icon="⌕" title="No requests yet" text="Add a request to get started." />}
        <div className="side-note"><strong>Prefer to browse first?</strong><p>Available items are also listed in Find items.</p><button className="text-button" onClick={() => setTab('browse')}>Browse items <b>→</b></button></div>
      </div>{needFormOpen && <div className="form-panel"><div className="form-title-row"><div><p className="eyebrow">START WITH WHAT WOULD HELP</p><h2>{editingNeed ? 'Edit request' : 'Add a request'}</h2></div><button className="button-quiet" type="button" onClick={() => { setNeedFormOpen(false); setEditingNeed(null) }}>Close</button></div><form key={editingNeed?.id||'new-need'} onSubmit={createNeed} className="form-grid">
        <label className="wide">Item or essential<input name="item_name" required maxLength={100} defaultValue={editingNeed?.item_name} placeholder="e.g. cookware, reading lamp" /></label>
        <label>Category<select name="category" required defaultValue={editingNeed?.category || 'Household'}>{['Household','Kitchen','Lighting','Furniture','Books','Clothing','Other'].map(x => <option key={x}>{x}</option>)}</select></label>
        <label>Quantity<input name="quantity" type="number" min="1" max="100" required defaultValue={editingNeed?.quantity ?? 1} /></label>
        <label>Arrival date<input name="arrival_date" type="date" required defaultValue={editingNeed?.arrival_date || isoOffset(7)} /></label>
        <label>Available from<input name="available_from" type="date" required defaultValue={editingNeed?.available_from || isoOffset(7)} /></label>
        <label>Available until<input name="available_until" type="date" required defaultValue={editingNeed?.available_until || isoOffset(10)} /></label>
        <label className="wide">General area<input name="area" required maxLength={80} defaultValue={editingNeed?.area} placeholder="e.g. East Rock" /></label>
        <details className="wide more-details" open={Boolean(editingNeed)}><summary>More details</summary><div className="form-grid"><label>Available from (local time)<input name="time_from" type="time" defaultValue={editingNeed?.time_from||''} /></label><label>Available until (local time)<input name="time_until" type="time" defaultValue={editingNeed?.time_until||''} /></label><label>Minimum condition<select name="preferred_condition" defaultValue={editingNeed?.preferred_condition || 'Fair'}>{['Any','Poor','Fair','Good','Like new'].map(x => <option key={x}>{x}</option>)}</select></label><label className="wide">Essential category<input name="essential_category" maxLength={60} defaultValue={editingNeed?.essential_category} placeholder="Only if the item must meet a category" /></label><label className="check-row wide"><input type="checkbox" name="has_vehicle" defaultChecked={editingNeed?.has_vehicle} /><span>I can transport a bulky item with a vehicle</span></label><label className="check-row wide"><input type="checkbox" name="requires_delivery" defaultChecked={editingNeed?.requires_delivery} /><span>I need delivery or another agreed transport arrangement</span></label></div></details>
        <div className="wide form-actions"><button className="button-primary" disabled={busy}>{busy ? 'Saving…' : editingNeed ? 'Save request' : 'Post request'} <span>↗</span></button>{editingNeed && <button type="button" className="button-quiet" onClick={() => { setEditingNeed(null); setNeedFormOpen(false) }}>Cancel edit</button>}</div>
      </form></div>}</section>}

      {planIsCurrent && plan && <PlanResult plan={plan} scope={planScope!} listings={[...ownListings,...listings]} needs={[...ownNeeds,...needs]} onRequest={id => { const item = [...ownListings,...listings].find(x => x.id===id); if (item) setRequestListing(item) }} />}

      {tab === 'handoffs' && <section className="handoff-list">
        <div className="handoff-filters" role="tablist" aria-label="Handoff status">
          {([['requested','Pending requests'],['reserved','Accepted reservations'],['completed','Completed pickups']] as const).map(([status,label]) => <button role="tab" aria-selected={handoffFilter===status} className={handoffFilter===status?'active':''} key={status} onClick={() => setHandoffFilter(status)}>{label}<span>{reservations.filter(r=>r.status===status).length}</span></button>)}
        </div>
        {handoffsToShow.length ? handoffsToShow.map(r => <article className="handoff-card" key={r.id}>
          <div className="handoff-icon">{r.status==='completed'?'✓':r.status==='reserved'?'↔':'…'}</div>
          <div className="handoff-body">
            <div className="row-between"><div><p className="eyebrow">{r.is_giver ? 'YOU’RE PASSING IT ON' : 'YOU REQUESTED'}</p><h3>{r.item_name} <small>× {r.quantity}</small></h3></div><StatusPill status={r.status} /></div>
            <p className="handoff-meta">{r.is_giver ? `With ${r.recipient_name}` : `From ${r.giver_name}`}</p>
            <ReservationPickup reservation={r} />
            {r.transport_plan && <p className="transport-note">↗ {r.transport_plan}</p>}
            {r.status==='requested' && r.is_giver && <div className="inline-actions">
              <button className="button-primary compact" onClick={() => decision(r.id,'accept')}>Accept request</button>
              {/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(r.pickup_window) && <button className="button-secondary compact" onClick={() => decision(r.id,'accept',r.pickup_window)}>Accept and agree to {pickupLabel(r.pickup_window)}</button>}
              <button className="button-quiet" onClick={() => decision(r.id,'decline')}>Decline</button>
            </div>}
            {r.status==='reserved' && <div className="confirm-box"><div><strong>Confirm only after the physical exchange.</strong><span>This records that the item changed hands; it does not agree to a future pickup.</span><div className="confirmation-state"><span>{r.giver_confirmed?'✓':'○'} Giver confirmed handoff</span><span>{r.recipient_confirmed?'✓':'○'} Recipient confirmed handoff</span></div></div>{(r.is_giver ? !r.giver_confirmed : !r.recipient_confirmed) && <button className="button-primary compact" onClick={() => confirmHandoff(r.id)}>{r.is_giver ? 'I have handed over the item.' : 'I have received the item.'}</button>}</div>}
            {r.status==='completed' && <p className="completed-copy">✓ Both people confirmed the completed physical exchange.</p>}
            {['requested','reserved'].includes(r.status) && <button className="text-button cancel-link" onClick={() => run(() => api(`/api/reservations/${r.id}/cancel`,{method:'POST'}),'Reservation canceled; the quantity is available again.')}>Cancel reservation <b>→</b></button>}
          </div>
        </article>) : <EmptyState icon="↔" title={handoffFilter==='requested'?'No pending requests':handoffFilter==='reserved'?'No accepted reservations':'No completed pickups'} text={handoffFilter==='requested'?'New item requests will appear here for you to review.':handoffFilter==='reserved'?'Accepted handoffs will stay here until both people confirm the physical exchange.':'Completed handoffs appear here after both people confirm.'} />}
      </section>}

      {tab === 'donate' && <section className="donate-layout"><div className="donate-intro"><span className="large-sprig">✳</span><p className="eyebrow">NEW HAVEN AREA</p><h3>Reuse, donation, and recycling resources.</h3><p>Use these official and organization sources to research a next step. Current item acceptance, condition rules, and schedules are unverified here; check each source before bringing anything.</p><button className="button-secondary" onClick={() => setTab('out')}>List an item <span>↗</span></button></div><div className="resource-list">{resources.map((r,i) => <article className="resource-card" key={r.id}><span className="resource-index">0{i+1}</span><div><p className="eyebrow">{r.category}</p><h3>{r.name}</h3>{r.location !== 'New Haven' && <p><strong>Location:</strong> {r.location}</p>}{r.accepted_items.length > 0 && <p><strong>Commonly exchanged examples:</strong> {r.accepted_items.join('; ')}.</p>}<p>{r.notes}</p><span className="verify-label">{r.acceptance_verified ? 'Acceptance details sourced' : 'Acceptance details need verification'}</span><a href={r.url} target="_blank" rel="noreferrer">Open official source <b>↗</b></a></div></article>)}</div></section>}

      {tab === 'evidence' && <Evidence usage={usage} completed={reservations.filter(r=>r.status==='completed').length} onReset={resetDemo} />}
    </main>
    <footer><div className="footer-brand">campusloop <span>↗</span></div><p>A student transition project for New Haven. Not an official Yale service. Demonstration names and listings are fictional.</p><span>Free to give · Thoughtful to receive</span></footer>

    {requestListing && <RequestModal item={requestListing} needs={ownNeeds} onClose={() => setRequestListing(null)} onSubmit={submitReservation} />}
    {loading && <div className="loading-bar" aria-label="Loading"><span /></div>}
  </div>
}

function ReservationPickup({ reservation: r }: { reservation: Reservation }) {
  const completed = r.status === 'completed'
  const hasSpecificProposal = /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(r.pickup_window)
  return <div className="reservation-pickup">
    <div><strong>General meeting area</strong><span>{r.area}</span></div>
    {r.status === 'requested' ? <div><strong>Recipient’s requested pickup</strong><span>{pickupLabel(r.pickup_window)}</span></div> : <div><strong>Pickup appointment</strong><span className={r.pickup_agreed ? 'pickup-confirmed' : 'pickup-unagreed'}>{r.pickup_agreed ? pickupLabel(r.pickup_window) : completed ? 'No pickup appointment was recorded.' : 'Reserved — pickup time not yet agreed'}</span></div>}
    <div><strong>Listing available</strong><span>{listingWindowLabel(r)}</span></div>
    {r.status === 'reserved' && !r.pickup_agreed && hasSpecificProposal && <small className="pickup-proposal">Recipient proposed {pickupLabel(r.pickup_window)}; the giver has not agreed to it.</small>}
  </div>
}

function Login({ onLogin, error, registering, setRegistering }: { onLogin: (email:string,password:string,form?:FormEvent)=>void; error:string; registering:boolean; setRegistering:(v:boolean)=>void }) {
  const [localError,setLocalError] = useState('')
  const [health,setHealth] = useState<{ai_configured:boolean;ai_status:string}|null>(null)
  useEffect(() => { api<typeof health>('/api/health').then(setHealth).catch(()=>undefined) }, [])
  async function register(e:FormEvent<HTMLFormElement>) {
    e.preventDefault(); setLocalError(''); const f=new FormData(e.currentTarget)
    try { const result=await api<{token:string;user:User}>('/api/auth/register',{method:'POST',body:JSON.stringify({email:f.get('email'),display_name:f.get('display_name'),password:f.get('password')})}); localStorage.setItem('campusloop-token',result.token); window.location.reload() }
    catch(e) { setLocalError((e as Error).message) }
  }
  return <div className="auth-screen"><div className="auth-art"><div className="brand auth-brand"><span className="brand-mark">↗</span><span>campusloop<small>pass it forward</small></span></div><div className="art-message"><span>✳</span><h1>Make room<br />for what’s next.</h1><p>Useful things deserve another chapter.<br />Let’s make the handoff work.</p></div><div className="art-foot"><span>NEW HAVEN, CONNECTED</span><span>01 — 02</span></div></div><section className="auth-panel"><div className="auth-form-wrap"><p className="eyebrow">WELCOME TO THE LOOP</p><h2>{registering ? 'Create your account.' : 'Pick up where you left off.'}</h2><p className="muted">{registering?'Make a local account to manage your listings and requests.':'Sign in to browse, list something, or request a handoff.'}</p>{(error||localError)&&<div className="inline-error" role="alert">{error||localError}</div>}
    {registering ? <form className="auth-form" onSubmit={register}><label>Your name<input name="display_name" required maxLength={80} /></label><label>Email<input name="email" type="email" required /></label><label>Password<input name="password" type="password" required minLength={12} /><small>At least 12 characters</small></label><button className="button-primary full-width">Create local account <span>↗</span></button></form> : <form className="auth-form" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);onLogin(String(f.get('email')),String(f.get('password')),e)}}><label>Email<input name="email" type="email" required defaultValue="incoming@campusloop.demo" /></label><label>Password<input name="password" type="password" required defaultValue="demo-incoming" /></label><button className="button-primary full-width">Sign in <span>↗</span></button></form>}
    {!registering && <div className="demo-access"><div><span className="demo-indicator"/><strong>Try the demo</strong><p>Fictional accounts — not verified Yale students.</p></div><div className="demo-buttons"><button onClick={()=>onLogin('outgoing@campusloop.demo','demo-outgoing')}>Giver side <span>↗</span></button><button onClick={()=>onLogin('incoming@campusloop.demo','demo-incoming')}>Recipient side <span>↗</span></button></div></div>}
    <button className="auth-switch" onClick={()=>{setRegistering(!registering);setLocalError('')}}>{registering?'Already have an account? Sign in':'New to CampusLoop? Create an account'}</button><p className="auth-disclaimer">CampusLoop is an independent local course prototype. It is not endorsed by Yale. Items and people marked demo are fictional.</p></div></section><div className="auth-ai">{health?.ai_configured?'✳ AI planner configured':'○ AI planner needs a Portkey key'} · Browsing and handoffs work either way</div></div>
}

function ListingCard({item,index,onRequest}:{item:Listing;index:number;onRequest:()=>void}) {
  const symbols=['⌂','✳','◌','↗','✣','⌁']
  return <article className={`listing-card card-${index%3}`}><div className="item-illustration"><span className="illustration-mark">{symbols[index%symbols.length]}</span><span className="item-category">{item.category}</span><span className="item-count">{item.remaining_quantity} left</span></div><div className="item-content"><div className="item-title-row"><h3>{item.item_name}</h3><StatusPill status={item.public_status} /></div><p className="item-description">{item.description || 'A useful item looking for its next home.'}</p><div className="item-specs"><span>◒ {item.condition}</span><span>⌖ {item.area}</span><span>↗ Until {dateLabel(item.pickup_deadline)}</span>{item.pickup_windows&&<span>◷ {item.pickup_windows}</span>}</div>{item.defects&&<p className="item-defect"><b>Good to know:</b> {item.defects}</p>}
      <div className="item-footer"><span className={item.requires_vehicle?'vehicle-tag':'carry-tag'}>{item.requires_vehicle?'🚙 Needs a vehicle':'↗ Easy to carry'}{item.requires_vehicle&&item.can_deliver?' · delivery may be possible':''}</span><button className="request-button" onClick={onRequest}>Request <span>↗</span></button></div>
      {item.is_demo&&<span className="demo-tag">DEMO LISTING</span>}
    </div></article>
}

function RequestModal({item,needs,onClose,onSubmit}:{item:Listing;needs:Need[];onClose:()=>void;onSubmit:(e:FormEvent<HTMLFormElement>)=>void}) {
  const [needId,setNeedId]=useState(needs[0]?.id||'')
  const need=needs.find(n=>n.id===needId)
  const min=[item.available_from,need?.available_from].filter(Boolean).sort().at(-1) || item.available_from
  const max=[item.pickup_deadline,need?.available_until].filter(Boolean).sort()[0] || item.pickup_deadline
  const froms=[item.time_from,need?.time_from].filter(Boolean)
  const untis=[item.time_until,need?.time_until].filter(Boolean)
  const timeMin=froms.length?froms.sort().at(-1)!:''
  const timeMax=untis.length?untis.sort()[0]:''
  const dateOverlap=min<=max
  const timeOverlap=!timeMin||!timeMax||timeMin<=timeMax
  const [pickupDate,setPickupDate]=useState(min)
  const [pickupTime,setPickupTime]=useState(timeMin)
  function changeNeed(id:string){
    setNeedId(id)
    const chosen=needs.find(n=>n.id===id)
    const nextMin=[item.available_from,chosen?.available_from].filter(Boolean).sort().at(-1)||item.available_from
    setPickupDate(nextMin)
    const starts=[item.time_from,chosen?.time_from].filter(Boolean).sort()
    setPickupTime(starts.at(-1)||'')
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><section className="request-modal" role="dialog" aria-modal="true" aria-labelledby="request-title"><button className="modal-close" onClick={onClose} aria-label="Close">×</button><p className="eyebrow">A CLEAR ASK MAKES A GOOD HANDOFF</p><h2 id="request-title">Request {item.item_name}</h2><p className="muted">The giver will review your request. It is not reserved until they accept.</p><div className="modal-item"><span>✳</span><div><strong>{item.item_name}</strong><small>{item.condition} · {item.area} · until {dateLabel(item.pickup_deadline)}</small></div></div><form className="modal-form" onSubmit={onSubmit}><label>Your need (optional)<select name="need_id" value={needId} onChange={e=>changeNeed(e.target.value)}><option value="">No posted need</option>{needs.map(n=><option value={n.id} key={n.id}>{n.item_name} · {dateLabel(n.available_from)} – {dateLabel(n.available_until)}</option>)}</select></label><div className="form-grid"><label>Pickup date<input name="pickup_date" type="date" required min={min} max={max} value={pickupDate} onChange={e=>setPickupDate(e.target.value)} /></label><label>Pickup time · New Haven<input name="pickup_time" type="time" min={timeMin||undefined} max={timeMax||undefined} required={Boolean(item.time_from||need?.time_from)} value={pickupTime} onChange={e=>setPickupTime(e.target.value)} /></label><label className="wide">Quantity<input name="quantity" type="number" min="1" max={Math.max(1,Math.min(item.remaining_quantity,10))} defaultValue="1" required /></label></div>{!dateOverlap&&<div className="transport-alert">Your dates and the listing dates do not overlap. No reservation can be requested for this item.</div>}{!timeOverlap&&<div className="transport-alert">The recorded pickup time windows do not overlap.</div>}{(item.requires_vehicle||need?.requires_delivery)&&<div className="transport-alert">This handoff needs a delivery agreement. The giver must explicitly accept the delivery request.</div>}<button className="button-primary full-width" disabled={!dateOverlap||!timeOverlap}>Send request <span>↗</span></button></form></section></div>
}
function StatusPill({status}:{status:string}) {
  const label:Record<string,string>={available:'Available',requested:'Requested',reserved:'Reserved',completed:'Completed',withdrawn:'Withdrawn',declined:'Declined',cancelled:'Cancelled'}
  return <span className={`status-pill status-${status}`}>{label[status]||status}</span>
}

function PlanResult({plan,scope,listings,needs,onRequest}:{plan:Plan;scope:{direction:'move_out'|'move_in';listingIds:string[];needIds:string[]};listings:Listing[];needs:Need[];onRequest:(id:string)=>void}) {
  const selectedNames = (scope.direction === 'move_out' ? scope.listingIds.map(id=>listings.find(x=>x.id===id)?.item_name) : scope.needIds.map(id=>needs.find(x=>x.id===id)?.item_name)).filter(Boolean)
  const purpose = scope.direction === 'move_out' ? 'Moving-out plan for' : 'Moving-in plan for'
  return <section className="plan-result"><div className="plan-top"><div><p className="eyebrow">{purpose} {selectedNames.join(', ')} · {plan.usage?.model||'AI planner'}</p><h2>{plan.direction==='move_in'?'A pickup plan you can act on.':'A next-home plan you can act on.'}</h2><p className="plan-scope-note">Generated for this account’s selected {scope.direction==='move_in'?'requests':'listings'}.</p></div><span className="plan-spark">✳</span></div><div className="plan-stats"><div><strong>{plan.matches.length}</strong><span>feasible matches</span></div><div><strong>{plan.unmatched.length}</strong><span>items with no match</span></div><div><strong>{plan.missing_info.length}</strong><span>details to clarify</span></div></div>
    {plan.matches.map((match,i)=><article className="plan-match" key={`${match.listing_id}-${match.need_id}`}><span className="match-number">0{i+1}</span><div><h3>{match.listing?.item_name||listings.find(x=>x.id===match.listing_id)?.item_name||'Handoff opportunity'}</h3><p>{match.need?.item_name||needs.find(x=>x.id===match.need_id)?.item_name||'Student need'} · {match.listing?.area||'Area to confirm'} · {match.quantity} item{match.quantity===1?'':'s'}</p><p>{match.why}</p>{(match.same_giver_group_size||0)>1&&<small>Grouped with other items from the same giver to simplify coordination.</small>}<small>{match.next_action}</small></div><button className="text-button" onClick={()=>onRequest(match.listing_id)}>Review item <b>→</b></button></article>)}
    {!!plan.possible_matches?.length&&<div className="missing-box"><strong>Possible matches that need a confirmation</strong>{plan.possible_matches.map((x,i)=><p key={i}>{x.issue} {x.next_action}</p>)}</div>}
    {plan.unmatched.length>0&&<div className="unmatched-box"><h3>{plan.direction==='move_in'?'Needs still unfilled':'Still looking for a next home'}</h3>{plan.unmatched.map(x=><p key={x.listing_id||x.need_id}><strong>{x.item_name}</strong> <span>— {x.reason}</span></p>)}</div>}
    {plan.resources.map(source=><div className="plan-source" key={source.resource_id}><strong>{source.name}</strong><span>{source.item?`${source.item}: `:''}{source.why} <b>Acceptance details need verification.</b></span><a href={source.url} target="_blank" rel="noreferrer">Check official source ↗</a></div>)}
    {plan.missing_info.length>0&&<div className="missing-box"><strong>Could use a little more detail</strong>{plan.missing_info.map((x,i)=><p key={i}>{x}</p>)}</div>}
    <p className="plan-disclaimer">{plan.action_summary||'A suggestion is not a reservation. Request the item and agree a pickup window with the other person.'}</p>
  </section>
}

function Evidence({usage,completed,onReset}:{usage:Usage|null;completed:number;onReset:()=>void}) {
  const requests=usage?.requests||[]
  const complete=requests.filter(r=>r.status==='success').length
  return <section className="evidence-view"><div className="evidence-summary"><div><p className="eyebrow">MEASURED ACTIVITY</p><h3>What the system has actually done.</h3><p>Only real model requests appear here. Missing provider fields stay marked unavailable.</p></div><div className="evidence-numbers"><span><strong>{complete}</strong> successful API requests</span><span><strong>{requests.length}</strong> measured request records</span><span><strong>{completed}</strong> confirmed handoffs</span></div></div><div className="usage-panel"><div className="panel-title"><span>◷</span><strong>Token and latency log</strong><small>{usage?.model||'gpt-6-luna'}</small></div>{requests.length?<div className="usage-table-wrap"><table><thead><tr><th>Time</th><th>Input</th><th>Cached</th><th>Output</th><th>Latency</th><th>Tools</th><th>Status</th></tr></thead><tbody>{requests.map((r,i)=><tr key={i}><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.input_tokens??'Unavailable'}</td><td>{r.cached_input_tokens??'Unavailable'}</td><td>{r.output_tokens??'Unavailable'}</td><td>{r.latency_ms==null?'Unavailable':`${r.latency_ms} ms`}</td><td title={r.tool_names?.join(', ')}>{r.tool_calls}{r.tool_names?.length ? <small>{r.tool_names.join(', ')}</small> : null}</td><td>{r.status}</td></tr>)}</tbody></table></div>:<EmptyState icon="◷" title="No measured API calls yet" text="A model request will appear only after an actual call." />}<div className="pricing-note"><span>!</span><p><strong>Cost figures are pending verification.</strong> {usage?.pricing_status||'No authoritative current Portkey pricing is recorded.'} Cached-token accounting must also be verified before estimating spend.</p></div><div className="scale-row">{['Typical run','1 user / month','100 users','10,000 users'].map((label,i)=><div key={label}><span>{label}</span><strong>—</strong><small>{i===1?`${usage?.scenario_assumption_runs_per_user_month||20} runs / month assumed`:'Cost pending'}</small></div>)}</div></div><div className="reset-panel"><div><strong>Restore demonstration records</strong><p>Removes/reset only fictional demo entries. Real user records are protected.</p></div><button className="button-quiet" onClick={onReset}>Reset demo data</button></div><div className="evidence-footnote">No AI suggestion counts as a reservation or completed reuse. Only a handoff confirmed by both people appears as completed.</div></section>
}

function EmptyState({icon,title,text}:{icon:string;title:string;text:string}) { return <div className="empty-state"><span>{icon}</span><strong>{title}</strong><p>{text}</p></div> }
