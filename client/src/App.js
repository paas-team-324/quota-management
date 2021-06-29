import React from 'react';
import './App.css';
import Auth from './Auth';
import UpdateQuota from './UpdateQuota';
import { Container, Toolbar, AppBar, Typography, Grid, Paper, Tab } from '@material-ui/core';
import { Alert, TabContext, TabPanel, TabList } from '@material-ui/lab';
import EditIcon from '@material-ui/icons/Edit';
import AddIcon from '@material-ui/icons/Add';

class App extends React.Component {
    constructor () {
        super();

        this.state = {
			authenticated: false,
            token: null,
			username: null,
			tab: 0,
			alerts: []
        };

		this.request = this.request.bind(this)
		this.addAlert = this.addAlert.bind(this)
		this.closeAlert = this.closeAlert.bind(this)
    };

	request(method, uri, query_params, data, callback) {

		// add auth token to query params
		query_params["token"] = this.state.token

		// prepare xhr request
		let xhr_request = new XMLHttpRequest()
		xhr_request.open(method, window.ENV.BACKEND_ROUTE + uri + "?" + new URLSearchParams(query_params).toString())

		// API response callback
		xhr_request.onreadystatechange = function() {

			if (xhr_request.readyState == XMLHttpRequest.DONE) {
				callback(xhr_request.responseText, (Math.floor(xhr_request.status / 100) == 2) )
			}

		}.bind(this)

		xhr_request.send(JSON.stringify(data))
	}

	addAlert(message, severity) {

		let alerts = this.state.alerts

		// push new alerts to alerts list
		alerts.push({
			"message": message,
			"severity": severity
		})

		// if more than three alerts - remove the oldest one
		if (alerts.length > 5) {
			alerts.shift()
		}

		this.setState({
			alerts: alerts,
		})

	}

	closeAlert(alert) {

		// get alert index
		let alerts = this.state.alerts
		let alertIndex = alerts.indexOf(alert)

		// delete alert by index
		if (alertIndex >= 0) {
			alerts.splice(alertIndex, 1)
		}

		// update alerts
		this.setState({
			alerts: alerts
		})
	}

    render () {
        return (
            <Container maxWidth="md">
                <AppBar color="primary">
                    <Toolbar>
						<Grid item xs={5}>
							<Typography variant="subtitle1">
								{ this.state.username }
							</Typography>
						</Grid>
						<Grid item xs={2}>
							<Typography variant="h6" align="center">
								Quota Management
							</Typography>
						</Grid>
                    </Toolbar>
                </AppBar>
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginTop: '15%'
                }}>
					<Container style={{
						justifyContent: 'center',
					}}>
						{this.state.authenticated ? (
							
							<TabContext value={this.state.tab}>
								<Paper square elevation={2}>
									<TabList
										indicatorColor="primary"
										textColor="primary"
										variant="fullWidth"
										onChange={(event, newValue) => {
											this.setState({
												tab: newValue
											})
										}}
									>
										<Tab label="Update Quota" icon={<EditIcon />} value={0}/>
									</TabList>
								</Paper>
								<Paper square elevation={2} style={{ marginTop: '1%' }}>
									<TabPanel value={0}>
										<UpdateQuota request={this.request} addAlert={this.addAlert}></UpdateQuota>
									</TabPanel>
								</Paper>
							</TabContext>

						) : (
							<Auth finishAuthentication={(token, username) => {
								this.setState({
									authenticated: true,
									username: username,
									token: token
								})
							}}></Auth>
						)}

						{this.state.alerts.map(alert => 
							<Grid item xs={12}>
								<Alert style={{ marginTop: '1%' }} severity={alert["severity"]} onClose={() => {this.closeAlert(alert)}}>{alert["message"]}</Alert>
							</Grid>
						)}
					</Container>
                </div>
            </Container>
        )
    }
}

export default App;