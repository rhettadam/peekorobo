import { Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { Home } from "./routes/Home";
import { Team } from "./routes/Team";
import { Event } from "./routes/Event";
import { Match } from "./routes/Match";
import { TeamHistory } from "./routes/TeamHistory";
import { TeamsLeaderboard } from "./routes/TeamsLeaderboard";
import { Events } from "./routes/Events";
import { Map } from "./routes/Map";
import { Compare } from "./routes/Compare";
import { Insights, InsightsSeason } from "./routes/Insights";
import { Login } from "./routes/Login";
import { Register } from "./routes/Register";
import { Profile } from "./routes/Profile";
import { PublicProfile } from "./routes/PublicProfile";
import { NotFound } from "./routes/NotFound";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Home />} />
        <Route path="teams" element={<TeamsLeaderboard />} />
        <Route path="team/:teamNumber" element={<Team />} />
        <Route path="team/:teamNumber/history" element={<TeamHistory />} />
        <Route path="team/:teamNumber/:year" element={<Team />} />
        <Route path="events" element={<Events />} />
        <Route path="event/:eventKey" element={<Event />} />
        <Route path="map" element={<Map />} />
        <Route path="match/:eventKey/:matchKey" element={<Match />} />
        <Route path="compare" element={<Compare />} />
        <Route path="insights" element={<Insights />} />
        <Route path="insights/:year" element={<InsightsSeason />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="user" element={<Profile />} />
        <Route path="user/:username" element={<PublicProfile />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
