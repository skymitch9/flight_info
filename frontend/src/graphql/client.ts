import { ApolloClient, InMemoryCache } from '@apollo/client';
import { HttpLink } from '@apollo/client/link/http';

const link = new HttpLink({
  uri: '/graphql',
});

const client = new ApolloClient({
  link,
  cache: new InMemoryCache(),
});

export default client;
