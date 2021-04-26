import React from 'react';
import './App.css';
import Auth from './Auth';
import { Container, Toolbar, AppBar, Typography, Box, makeStyles } from '@material-ui/core';

class App extends React.Component {
  constructor () {
    super();
    this.state = {
      token: null,
      project_list: null,
      scheme: null,
      authenticated: false
    };
    
    // container styling
    this.classes = makeStyles(theme => ({

      root: {
        width: '90%',
      },
      button: {
        marginTop: theme.spacing(1),
        marginRight: theme.spacing(1),
      },
      actionsContainer: {
        marginBottom: theme.spacing(2),
      },
      resetContainer: {
        padding: theme.spacing(3),
      },
    }));

    this.finishAuthentication = this.finishAuthentication.bind(this)
  };

  finishAuthentication(token, project_list, scheme) {
    this.setState({
      token: token,
      project_list: project_list,
      scheme: scheme,
      authenticated: true
    })
  }

  render () {
    return (
      <Container maxWidth="md">
        <AppBar color="primary">
          <Toolbar style={{display: "grid"}}>
            <Typography variant="h6" align="center">
            Quota Management
            </Typography>
          </Toolbar>
        </AppBar>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: '15%'
        }}>
          {this.state.authenticated ? (
            <div>Very nice</div>
          ) : (
            <Auth token={this.state.token} project_list={this.state.project_list} scheme={this.state.scheme} finishAuthentication={this.finishAuthentication}></Auth>
          )}
        </div>
      </Container>
    )
  }
}

export default App;