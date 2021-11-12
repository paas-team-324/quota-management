import React from 'react';
import './App.css';
import Auth from './Auth';
import Cluster from './Cluster';
import { Container, Toolbar, AppBar, Typography, Grid, Button, Dialog, DialogTitle, List, ListItem, ListItemText } from '@material-ui/core';
import { createMuiTheme, ThemeProvider } from '@material-ui/core';
import { Alert, AlertTitle } from '@material-ui/lab';
import ListIcon from '@material-ui/icons/List';

// true - production color theme, false - dev color theme
const colorThemes = {
	true: createMuiTheme( { palette: { primary: { main: "#b71c1c" } } } ),
	false: createMuiTheme( { palette: { primary: { main: "#1565c0" } } } )
}

class App extends React.Component {
    constructor () {
        super();

        this.state = {
			authenticated: false,
            token: null,
			username: null,
			clusters: {},
			cluster: null,
			cluster_dialog_open: false,
			error: null,
			colorTheme: colorThemes[false],

			alerts: []
        };

		this.update_clusters_list = this.update_clusters_list.bind(this)
		this.request = this.request.bind(this)
		this.addAlert = this.addAlert.bind(this)
		this.closeAlert = this.closeAlert.bind(this)
    };

	update_clusters_list() {

		// fetch clusters
		this.request('GET', '/clusters', {}, {}, function(response, ok) {

			let clusters = JSON.parse(response)

			if (ok) {

				// make sure there are any clusters
				if (clusters.length == 0) {
					this.setState({
						error: "There are no available clusters"
					})
				} else {
					this.setState({
						clusters: clusters,
						cluster_dialog_open: true
					})
				}

			} else {
				this.setState({
					error: clusters["message"]
				})
			}

		}.bind(this))

	}

	request(method, uri, query_params, data, callback) {

		// add auth token and cluster to query params
		query_params["token"] = this.state.token
		query_params["cluster"] = this.state.cluster

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
			<ThemeProvider theme={this.state.colorTheme}>
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
								
								<span>

									{this.state.error == null ? (

										<span>

											<Dialog open={this.state.cluster_dialog_open}>
												<DialogTitle>Choose cluster</DialogTitle>
												<List sx={{ pt: 0 }}>
													{Object.keys(this.state.clusters).map((cluster) => (
														<ListItem button onClick={() => {
															this.setState({
																cluster: cluster,
																colorTheme: colorThemes[this.state.clusters[cluster]["production"]],
																cluster_dialog_open: false,
															})
														}}>
															<ListItemText primary={this.state.clusters[cluster]["displayName"]} />
														</ListItem>
													))}
												</List>
											</Dialog>

											{this.state.cluster != null && (

												<span>
													<Button
														size="large"
														variant="outlined"
														color="primary"
														component="span"
														fullWidth
														startIcon={<ListIcon />}
														onClick={() => this.setState({cluster_dialog_open: true})}>
														{this.state.clusters[this.state.cluster]["displayName"]}
													</Button>
													<Cluster request={this.request} addAlert={this.addAlert} cluster={this.state.cluster}></Cluster>
												</span>

											)}

										</span>

									) : (
										<Grid item xs={12}>
											<Alert severity="error">
												<AlertTitle>Error</AlertTitle>
												{this.state.error}
											</Alert>
										</Grid>
									)}

								</span>

							) : (
								<Auth finishAuthentication={(token, username) => {
									this.setState({
										authenticated: true,
										username: username,
										token: token
									}, function() {
										this.update_clusters_list()
									}.bind(this))
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
			</ThemeProvider>
        )
    }
}

export default App;