import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Button } from './button';

describe('Button', () => {
  it('renders an accessible native button', () => {
    expect(renderToStaticMarkup(<Button type="button">Continue</Button>)).toContain(
      'type="button"',
    );
  });
});
