import { register } from 'node:module'

register(new URL('./node-loader.mjs', import.meta.url))
