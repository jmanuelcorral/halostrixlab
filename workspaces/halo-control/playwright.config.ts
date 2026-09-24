import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/browser',use:{baseURL:'http://127.0.0.1:4173',headless:true,viewport:{width:1440,height:1000}},webServer:{command:'./node_modules/.bin/vite preview --host 127.0.0.1 --port 4173',port:4173,reuseExistingServer:false},reporter:'list'});
