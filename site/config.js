(() => {
  const host = window.location.hostname.toLowerCase();
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const isGitHubPages = host.endsWith('.github.io') && pathParts.length > 0;
  const owner = isGitHubPages ? host.split('.')[0] : 'Flowrbanbetareports';
  const repositoryName = isGitHubPages ? pathParts[0] : 'ThisTinti';
  window.THISTINTI_SITE = {
    repository: `${owner}/${repositoryName}`,
    projectName: 'ThisTinti',
  };
})();
