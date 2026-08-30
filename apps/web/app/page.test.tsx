import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import HomePage from './page';

describe('RecoveryOS home page', () => {
  it('renders the repository baseline message', () => {
    const markup = renderToStaticMarkup(HomePage());
    expect(markup).toContain('Revenue recovery control plane');
  });
});
