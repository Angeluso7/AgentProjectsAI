import esbuild from 'esbuild';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  const outfile = path.resolve(__dirname, 'temp_render_test.mjs');
  await esbuild.build({
    entryPoints: [path.resolve(__dirname, 'test_pipeline_navigation_and_rendering.tsx')],
    bundle: true,
    platform: 'node',
    packages: 'external',
    format: 'esm',
    outfile: outfile,
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://localhost:8000/api/v1')
    }
  });

  const child = spawn('node', [outfile], { stdio: 'inherit' });
  child.on('exit', (code) => {
    try {
      if (fs.existsSync(outfile)) {
        fs.unlinkSync(outfile);
      }
    } catch {}
    process.exit(code || 0);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
