import express from 'express';
import path from 'node:path';

const app = express();
const port = process.env.UI_PORT || 4200;
const staticDir = path.resolve(process.cwd(), 'src');

app.use(express.static(staticDir));
app.listen(port, () => console.log(`ProjectHearth UI on ${port}`));
