'use strict';

const { config, t } = FPPApp;
const locale = FPPApp.locale;
const headline = document.getElementById('headline');
const backHome = document.getElementById('back-home');


headline.textContent = FPPApp.siteName;

backHome.addEventListener('click', () => {
  window.location.href = '/';
});

// Configuration
const MAX_RECENT_SONGS_DISPLAY = 20;

// Chart colors
const chartColors = [
  'rgba(255, 99, 132, 0.8)',
  'rgba(54, 162, 235, 0.8)',
  'rgba(255, 206, 86, 0.8)',
  'rgba(75, 192, 192, 0.8)',
  'rgba(153, 102, 255, 0.8)',
  'rgba(255, 159, 64, 0.8)',
  'rgba(199, 199, 199, 0.8)',
  'rgba(83, 102, 255, 0.8)'
];

const chartBorderColors = [
  'rgba(255, 99, 132, 1)',
  'rgba(54, 162, 235, 1)',
  'rgba(255, 206, 86, 1)',
  'rgba(75, 192, 192, 1)',
  'rgba(153, 102, 255, 1)',
  'rgba(255, 159, 64, 1)',
  'rgba(199, 199, 199, 1)',
  'rgba(83, 102, 255, 1)'
];

function formatTimestamp(isoString) {
  if (!isoString) return t('stats.unknown');
  try {
    const date = new Date(isoString);
    return date.toLocaleString(locale, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return t('stats.unknown');
  }
}

function formatDuration(sec) {
  if (typeof sec !== 'number' || Number.isNaN(sec) || sec === 0) return t('stats.unknown');
  const minutes = Math.floor(sec / 60);
  const seconds = String(Math.floor(sec % 60)).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function groupByDate(timeline) {
  const grouped = {};
  timeline.forEach(entry => {
    const date = entry.timestamp ? new Date(entry.timestamp).toLocaleDateString(locale) : t('stats.unknown');
    if (!grouped[date]) {
      grouped[date] = 0;
    }
    grouped[date]++;
  });
  return grouped;
}

// Values come from stored visitor input: always insert as text, never as HTML.
function appendCells(row, values) {
  values.forEach((value) => {
    const cell = document.createElement('td');
    cell.textContent = String(value);
    row.appendChild(cell);
  });
}

// Year selection: no parameter = current year; past years form the archive.
const yearSelect = document.getElementById('stats-year-select');
const requestedYear = new URLSearchParams(location.search).get('year');

function renderYearSelect(data) {
  yearSelect.replaceChildren();
  const current = document.createElement('option');
  current.value = String(data.currentYear);
  current.textContent = t('stats.current', { year: data.currentYear });
  yearSelect.appendChild(current);
  const past = (data.years || []).filter((y) => y !== data.currentYear);
  if (past.length) {
    const group = document.createElement('optgroup');
    group.label = t('stats.archive');
    past.forEach((y) => {
      const option = document.createElement('option');
      option.value = String(y);
      option.textContent = String(y);
      group.appendChild(option);
    });
    yearSelect.appendChild(group);
  }
  yearSelect.value = String(data.year);

  const isArchive = data.year !== data.currentYear;
  document.getElementById('stats-subtitle').textContent = isArchive ? t('stats.subtitleArchive', { year: data.year }) : t('stats.subtitleCurrent', { year: data.year });
  const archiveNote = document.getElementById('stats-archive-note');
  archiveNote.textContent = t('stats.archiveNote', { year: data.year });
  archiveNote.classList.toggle('hidden', !isArchive);

  const empty = (data.show_starts || {}).total === 0 && (data.song_requests || {}).total === 0;
  const emptyNote = document.getElementById('stats-empty');
  emptyNote.textContent = isArchive
    ? t('stats.emptyArchive', { year: data.year })
    : t('stats.emptyCurrent', { year: data.year });
  emptyNote.classList.toggle('hidden', !empty);
}

yearSelect.addEventListener('change', () => {
  const url = new URL(location.href);
  if (yearSelect.value === yearSelect.options[0].value) url.searchParams.delete('year');
  else url.searchParams.set('year', yearSelect.value);
  location.href = url.toString();
});

async function loadStatistics() {
  try {
    const query = requestedYear && /^\d{4}$/.test(requestedYear) ? `?year=${requestedYear}` : '';
    const response = await fetch(`/api/statistics${query}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderYearSelect(data);

    // Show Statistics
    const showStarts = data.show_starts || {};
    document.getElementById('total-shows').textContent = showStarts.total || 0;

    // Shows Pie Chart
    const showsByPlaylist = showStarts.by_playlist || {};
    const showPlaylists = Object.keys(showsByPlaylist);
    const showCounts = Object.values(showsByPlaylist);

    if (showPlaylists.length > 0) {
      new Chart(document.getElementById('showsPieChart'), {
        type: 'pie',
        data: {
          labels: showPlaylists,
          datasets: [{
            data: showCounts,
            backgroundColor: chartColors,
            borderColor: chartBorderColors,
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: 'rgba(255, 255, 255, 0.92)'
              }
            }
          }
        }
      });
    }

    // Shows Line Chart
    const showTimeline = showStarts.timeline || [];
    const showsByDate = groupByDate(showTimeline);
    const showDates = Object.keys(showsByDate).sort();
    const showDateCounts = showDates.map(date => showsByDate[date]);

    if (showDates.length > 0) {
      new Chart(document.getElementById('showsLineChart'), {
        type: 'line',
        data: {
          labels: showDates,
          datasets: [{
            label: t('stats.showStarts'),
            data: showDateCounts,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 2,
            tension: 0.1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              labels: {
                color: 'rgba(255, 255, 255, 0.92)'
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)',
                stepSize: 1
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            },
            x: {
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)'
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            }
          }
        }
      });
    }

    // Shows Table
    const showsTbody = document.getElementById('shows-tbody');
    if (showTimeline.length > 0) {
      showsTbody.innerHTML = '';
      // Show most recent first
      const recentShows = [...showTimeline].reverse();
      recentShows.forEach(entry => {
        const row = document.createElement('tr');
        appendCells(row, [formatTimestamp(entry.timestamp), entry.playlist || t('stats.unknown')]);
        showsTbody.appendChild(row);
      });
    }

    // Song Request Statistics
    const songRequests = data.song_requests || {};
    document.getElementById('total-songs').textContent = songRequests.total || 0;

    // Top 5 Songs Bar Chart
    const top5 = songRequests.top_5 || [];
    if (top5.length > 0) {
      new Chart(document.getElementById('songsTopChart'), {
        type: 'bar',
        data: {
          labels: top5.map(s => s.song),
          datasets: [{
            label: t('stats.requestCount'),
            data: top5.map(s => s.count),
            backgroundColor: chartColors[0],
            borderColor: chartBorderColors[0],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              labels: {
                color: 'rgba(255, 255, 255, 0.92)'
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)',
                stepSize: 1
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            },
            x: {
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)'
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            }
          }
        }
      });
    }

    // Songs Line Chart
    const songTimeline = songRequests.timeline || [];
    const songsByDate = groupByDate(songTimeline);
    const songDates = Object.keys(songsByDate).sort();
    const songDateCounts = songDates.map(date => songsByDate[date]);

    if (songDates.length > 0) {
      new Chart(document.getElementById('songsLineChart'), {
        type: 'line',
        data: {
          labels: songDates,
          datasets: [{
            label: t('stats.songRequests'),
            data: songDateCounts,
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 2,
            tension: 0.1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              labels: {
                color: 'rgba(255, 255, 255, 0.92)'
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)',
                stepSize: 1
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            },
            x: {
              ticks: {
                color: 'rgba(255, 255, 255, 0.92)'
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              }
            }
          }
        }
      });
    }

    // All Songs Table
    const songsBySong = songRequests.by_song || {};
    const songsTbody = document.getElementById('songs-tbody');
    const songEntries = Object.entries(songsBySong).sort((a, b) => b[1].count - a[1].count);
    
    if (songEntries.length > 0) {
      songsTbody.innerHTML = '';
      songEntries.forEach(([song, data]) => {
        const row = document.createElement('tr');
        appendCells(row, [song, data.count]);
        songsTbody.appendChild(row);
      });
    }

    // Recent Songs Table
    const recentSongsTbody = document.getElementById('recent-songs-tbody');
    if (songTimeline.length > 0) {
      recentSongsTbody.innerHTML = '';
      // Show most recent first
      const recentSongs = [...songTimeline].reverse().slice(0, MAX_RECENT_SONGS_DISPLAY);
      recentSongs.forEach(entry => {
        const row = document.createElement('tr');
        appendCells(row, [formatTimestamp(entry.timestamp), entry.song_title || t('stats.unknown'), formatDuration(entry.duration)]);
        recentSongsTbody.appendChild(row);
      });
    }

  } catch (err) {
    console.error('Could not load the statistics:', err);
    document.getElementById('total-shows').textContent = t('stats.error');
    document.getElementById('total-songs').textContent = t('stats.error');
  }
}

FPPApp.renderSocialFooter();
loadStatistics();
