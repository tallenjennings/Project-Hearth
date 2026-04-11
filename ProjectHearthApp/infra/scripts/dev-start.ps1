Write-Host "Starting ProjectHearthApp local dev services..."
Copy-Item -Path .env.example -Destination .env -ErrorAction SilentlyContinue
npm install
npm run dev:api
