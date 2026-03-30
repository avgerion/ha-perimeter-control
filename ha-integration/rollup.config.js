import resolve from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';

const dev = process.env.ROLLUP_WATCH === 'true';

export default {
    input: 'src/index.ts',
    output: {
        file: 'dist/ha-integration.js',
        format: 'es',
        sourcemap: dev,
    },
    plugins: [
        resolve(),
        typescript({
            tsconfig: './tsconfig.json',
            // Inline declarations into the bundle; no separate .d.ts needed for HA card
            declaration: false,
            declarationMap: false,
        }),
        !dev && terser({ format: { comments: false } }),
    ].filter(Boolean),
    // Don't try to bundle Node built-ins used only in deploy.py (not in browser code)
    external: [],
};
