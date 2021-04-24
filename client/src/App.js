import React from 'react';
import './App.css';
import { Container, Toolbar, AppBar, Typography, makeStyles } from '@material-ui/core';

class App extends React.Component {
  constructor () {
    super();
    this.state = {

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
  };

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
      </Container>
    )
  }
}

export default App;