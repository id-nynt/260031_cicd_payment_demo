// Experiment release identity is part of the application commit, not a runtime override.
// Freeze a new v1 commit/tag, then change only this value to 'v2' for its candidate.
export const APP_VERSION: 'v1' | 'v2' = 'v2';

export const releaseBanner = `<header aria-label="Application version" style="padding:16px 20px;margin-bottom:24px;border:2px solid #155eef;border-radius:10px;background:#e7efff;color:#123c8c"><strong style="font-size:24px">Payment Service <span style="display:inline-block;padding:2px 10px;margin-left:8px;border-radius:6px;background:#155eef;color:#fff">${APP_VERSION}</span></strong></header>`;
