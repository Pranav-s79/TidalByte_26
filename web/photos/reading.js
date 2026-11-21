const api = '/api/piney-point/reading';
const field = (id) => document.getElementById(id);
const button = field('analyze');
const localTime = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Chicago'
});

function showReading(reading, source) {
  field('model').textContent = reading.model.split('/').pop();
  field('water').textContent = reading.water_visible ? 'Visible' : 'None seen';
  const hasRange = Number.isFinite(reading.depth_m_low) && Number.isFinite(reading.depth_m_high);
  field('depth').textContent = hasRange
    ? reading.depth_m_low.toFixed(2) + '–' + reading.depth_m_high.toFixed(2) + ' m' : 'Unknown';
  field('reason').textContent = reading.reasoning || 'No visual assessment was returned.';
  field('reference').textContent = reading.reference_object || 'None identified';
  field('confidence').textContent = reading.confidence.charAt(0).toUpperCase() + reading.confidence.slice(1);
  field('review').textContent = reading.status === 'needs_review' ? 'Needs review' : 'Awaiting review';
  field('review').hidden = false;
  field('issue').textContent = reading.error || '';
  field('issue').hidden = !reading.error;
  const objects = reading.detector?.objects;
  field('detector').textContent = !Array.isArray(objects) ? 'Unavailable'
    : objects.length ? objects.map(o => o.label + ' (' + Math.round(o.score * 100) + '%)').join(', ')
    : 'No matching objects';
  field('stamp').textContent = source + ' · ' + localTime.format(new Date(reading.analyzed_at))
    + ' CT · ' + reading.elapsed_s + ' s';
}

async function connect() {
  showReading(recordedReading, 'Saved reading');
  if (location.protocol === 'file:') return;
  try {
    const response = await fetch(api, {cache: 'no-store'});
    if (!response.ok || !response.headers.get('Content-Type')?.includes('application/json')) return;
    const {reading} = await response.json();
    if (reading) showReading(reading, 'Last server run');
    button.hidden = false;
  } catch {
    // A static copy can display the recorded response offline.
  }
}

button.addEventListener('click', async () => {
  button.disabled = true;
  button.textContent = 'Analyzing photo…';
  field('status').textContent = 'Running the detector and Nemotron on the 2017 photograph…';
  try {
    const response = await fetch(api, {method: 'POST'});
    if (!response.headers.get('Content-Type')?.includes('application/json')) {
      throw new Error('The live server is unavailable. The previous reading is still displayed.');
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The live request failed. Please retry.');
    showReading(data.reading, 'Live model run');
    field('status').textContent = 'New reading ready for review.';
  } catch (err) {
    field('status').textContent = err instanceof TypeError
      ? 'Could not reach the live server. The previous reading is still displayed.' : err.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Run live reading ↗';
  }
});
connect();
