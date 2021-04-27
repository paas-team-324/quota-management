import React from 'react';
import './App.css';
import Auth from './Auth';
import ResourceQuota from './ResourceQuota';
import { Container, Toolbar, AppBar, Typography, Select, makeStyles } from '@material-ui/core';

class App extends React.Component {
  constructor () {
    super();
    this.state = {
      token: null,
      project_list: null,
      scheme: null,
      authenticated: false,
      project: null
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
      authenticated: true,
      project: project_list[0]
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
            <Container>
              <Typography variant="h6" style={{ marginRight: "3px" }} gutterBottom>
                Project: 
                <Select
                  native
                  value={this.state.project}
                  onChange={(event) => {
                      this.setState({
                          project: event.target.value
                      })
                  }}
                >
                  {this.state.project_list.map(project =>
                      <option key={project} value={project}>{project}</option>)}
                </Select>
                </Typography>
              {Object.keys(this.state.scheme).map(quota_object_name =>
                  <ResourceQuota name={quota_object_name} fields={this.state.scheme[quota_object_name]}></ResourceQuota>)}
            </Container>
           ) : (
            <Auth token={this.state.token} project_list={this.state.project_list} scheme={this.state.scheme} finishAuthentication={this.finishAuthentication}></Auth>
          )}
        </div>
      </Container>
    )
  }
}

export default App;