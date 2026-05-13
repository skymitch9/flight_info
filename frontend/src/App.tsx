import { ApolloProvider } from '@apollo/client/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import client from './graphql/client';
import TripList from './pages/TripList';
import TripDetail from './pages/TripDetail';

function App() {
  return (
    <ApolloProvider client={client}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TripList />} />
          <Route path="/trips/:id" element={<TripDetail />} />
        </Routes>
      </BrowserRouter>
    </ApolloProvider>
  );
}

export default App;
