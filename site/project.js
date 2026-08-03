(() => {
  'use strict';

  const repo = window.THISTINTI_SITE?.repository;
  const byId = (id) => document.getElementById(id);
  const number = (value) => new Intl.NumberFormat('it-IT').format(Number(value || 0));
  const apiHeaders = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };

  function category(name) {
    const value = String(name || '').toLowerCase();
    if (value.startsWith('thistinti-setup-') && value.endsWith('.exe')) return 'installer';
    if (value.startsWith('thistinti-portable-') && value.endsWith('.zip')) return 'portable';
    if (value.includes('self-hosted-source') && value.endsWith('.zip')) return 'selfHosted';
    if (value.includes('integration-pack') && value.endsWith('.zip')) return 'integrationPack';
    return null;
  }

  async function github(path) {
    const response = await fetch(`https://api.github.com/repos/${repo}${path}`, { headers: apiHeaders });
    if (!response.ok) throw new Error(`GitHub API ${response.status}`);
    return response.json();
  }

  function summarize(repoData, releases, actions) {
    const totals = { installer: 0, portable: 0, selfHosted: 0, integrationPack: 0, allAssets: 0 };
    const releaseRows = releases.map((release) => {
      const row = { installer: 0, portable: 0, selfHosted: 0, integrationPack: 0, allAssets: 0 };
      for (const asset of release.assets || []) {
        const count = Number(asset.download_count || 0);
        row.allAssets += count;
        totals.allAssets += count;
        const kind = category(asset.name);
        if (kind) {
          row[kind] += count;
          totals[kind] += count;
        }
      }
      row.product = row.installer + row.portable + row.selfHosted + row.integrationPack;
      return { tag: release.tag_name, publishedAt: release.published_at, url: release.html_url, ...row };
    });
    totals.product = totals.installer + totals.portable + totals.selfHosted + totals.integrationPack;
    return {
      totals,
      releases: releaseRows,
      repository: {
        stars: repoData.stargazers_count || 0,
        forks: repoData.forks_count || 0,
        openItems: repoData.open_issues_count || 0,
        watchers: repoData.subscribers_count || 0,
      },
      workflows: (actions.workflow_runs || []).slice(0, 10),
    };
  }

  function set(id, value) { byId(id).textContent = value; }

  function render(data) {
    set('productDownloads', number(data.totals.product));
    set('installerDownloads', number(data.totals.installer));
    set('portableDownloads', number(data.totals.portable));
    set('selfHostedDownloads', number(data.totals.selfHosted));
    set('projectStars', number(data.repository.stars));
    set('projectReleases', number(data.releases.length));
    set('projectForks', number(data.repository.forks));
    set('projectOpenItems', number(data.repository.openItems));
    set('projectWatchers', number(data.repository.watchers));
    set('allAssetDownloads', number(data.totals.allAssets));
    set('metricsUpdatedAt', `Aggiornato ${new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date())}`);

    const tableBody = byId('releaseDownloadRows');
    const rows = data.releases.map((release) => {
      const row = document.createElement('tr');
      for (const value of [release.tag || '—', release.installer, release.portable, release.selfHosted, release.product]) {
        const cell = document.createElement('td');
        cell.textContent = typeof value === 'number' ? number(value) : value;
        row.appendChild(cell);
      }
      return row;
    });
    if (rows.length) tableBody.replaceChildren(...rows);
    else {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 5;
      cell.textContent = 'Nessuna release rilevata.';
      row.appendChild(cell);
      tableBody.replaceChildren(row);
    }

    const workflowList = byId('projectWorkflows');
    const workflowRows = data.workflows.map((workflow) => {
      const row = document.createElement('div');
      row.className = 'project-workflow';
      const name = document.createElement('strong');
      name.textContent = workflow.name || 'Workflow';
      const status = document.createElement('span');
      const running = workflow.status === 'in_progress';
      status.className = running ? 'running' : (workflow.conclusion || '');
      status.textContent = running ? 'in corso' : (workflow.conclusion || workflow.status || '—');
      row.append(name, status);
      return row;
    });
    if (workflowRows.length) workflowList.replaceChildren(...workflowRows);
    else {
      const empty = document.createElement('p');
      empty.textContent = 'Nessun workflow rilevato.';
      workflowList.replaceChildren(empty);
    }
  }

  async function load() {
    const status = byId('projectStatus');
    const button = byId('refreshProjectMetrics');
    if (!repo || !repo.includes('/')) {
      status.textContent = 'Repository non configurato.';
      status.className = 'project-status error';
      return;
    }
    button.disabled = true;
    button.textContent = 'Aggiornamento…';
    status.textContent = 'Lettura dei dati pubblici GitHub…';
    status.className = 'project-status';
    try {
      const [repoData, releases, actions] = await Promise.all([
        github(''),
        github('/releases?per_page=100'),
        github('/actions/runs?per_page=20'),
      ]);
      render(summarize(repoData, releases, actions));
      status.textContent = 'Dati pubblici aggiornati. Nessuna telemetria dell’app è coinvolta.';
      status.className = 'project-status success';
    } catch (error) {
      status.textContent = `Metriche temporaneamente non disponibili: ${error.message}`;
      status.className = 'project-status error';
    } finally {
      button.disabled = false;
      button.textContent = 'Aggiorna';
    }
  }

  byId('refreshProjectMetrics').addEventListener('click', load);
  load();
})();
