'use strict';

const { config } = FPPApp;
const headline = document.getElementById('headline');
const backHome = document.getElementById('back-home');

FPPApp.access.redirectIfMissing();

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
  if (!isoString) return 'Unbekannt';
  try {
    const date = new Date(isoString);
    return date.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return 'Unbekannt';
  }
}

function formatDuration(sec) {
  if (typeof sec !== 'number' || Number.isNaN(sec) || sec === 0) return 'unbekannt';
  const minutes = Math.floor(sec / 60);
  const seconds = String(Math.floor(sec % 60)).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function groupByDate(timeline) {
  const grouped = {};
  timeline.forEach(entry => {
    const date = entry.timestamp ? new Date(entry.timestamp).toLocaleDateString('de-DE') : 'Unbekannt';
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

async function loadStatistics() {
  try {
    const response = await fetch('/api/statistics');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

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
            label: 'Show-Starts',
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
        appendCells(row, [formatTimestamp(entry.timestamp), entry.playlist || 'Unbekannt']);
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
            label: 'Anzahl Wünsche',
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
            label: 'Liedwünsche',
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
        appendCells(row, [formatTimestamp(entry.timestamp), entry.song_title || 'Unbekannt', formatDuration(entry.duration)]);
        recentSongsTbody.appendChild(row);
      });
    }

  } catch (err) {
    console.error('Fehler beim Laden der Statistiken:', err);
    document.getElementById('total-shows').textContent = 'Fehler';
    document.getElementById('total-songs').textContent = 'Fehler';
  }
}

FPPApp.renderSocialFooter();
loadStatistics();
