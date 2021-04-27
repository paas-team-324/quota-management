import React from 'react';
import { Typography } from '@material-ui/core';

class Auth extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            token: null,
            project_list: null,
            error: false,
            message: "Authenticating..."
        };
    };

    // begin authentication
    componentDidMount() {
        
        // access token is passed in the anchor field for some reason
        let queryString = window.location.hash.replace(/^#/, '?')
        let urlParams = new URLSearchParams(queryString)

        // use token to request project list
        if (urlParams.has('access_token')) {

            // store token
            this.setState({
                token: urlParams.get('access_token'),
                message: "Fetching projects..."
            })

            // prepare URL params
            let xhr_projects_params = new URLSearchParams({
                token: urlParams.get('access_token')
            })

            // prepare API request for projects
            let xhr_projects = new XMLHttpRequest()
            xhr_projects.open('GET', window.ENV.BACKEND_ROUTE + "/projects?" + xhr_projects_params.toString())

            // API response callback
            xhr_projects.onreadystatechange = function () {
                if (xhr_projects.readyState == XMLHttpRequest.DONE) {
                    if (xhr_projects.status == 200) {

                        let project_list = JSON.parse(xhr_projects.responseText)["projects"]

                        // make sure there is at least one managed project
                        if (project_list.length == 0) {

                            this.setState({
                                error: true,
                                message: "there are no managed projects that exist in this cluster"
                            })

                        } else {

                            // store project list
                            this.setState({
                                project_list: project_list,
                                message: "Fetching quota scheme..."
                            })

                            // prepare API request for quota projects
                            let xhr_scheme = new XMLHttpRequest()
                            xhr_scheme.open('GET', window.ENV.BACKEND_ROUTE + "/scheme")

                            // API response callback
                            xhr_scheme.onreadystatechange = function () {
                                if (xhr_scheme.readyState == XMLHttpRequest.DONE) {
                                    if (xhr_scheme.status == 200) {

                                        // finish authentication
                                        this.props.finishAuthentication(this.state.token, this.state.project_list, JSON.parse(xhr_scheme.responseText))

                                    } else {

                                        this.setState({
                                            error: true,
                                            message: JSON.parse(xhr_projects.responseText)["message"]
                                        })

                                    }
                                }
                            }.bind(this)

                            xhr_scheme.send()

                        }

                    } else {

                        this.setState({
                            error: true,
                            message: JSON.parse(xhr_projects.responseText)["message"]
                        })

                    }
                }
            }.bind(this)

            xhr_projects.send()
        }

        // redirect to authentication screen if access token is not present
        else {
            let redirectUrl = window.ENV.OAUTH_ENDPOINT + '/oauth/authorize?'

            // parameters passed to OpenShift OAuth server
            let redirectParams = new URLSearchParams({
                client_id: window.ENV.OAUTH_CLIENT_ID,
                redirect_uri: window.location.origin,
                response_type: 'token'
            })

            // redirect to OAuth server
            window.location.replace(redirectUrl + redirectParams.toString())
        }
    }

    render() {

        if (this.state.error == true) {
            return (
                <Typography color="error">
                    <div>
                        Error: {this.state.message}
                    </div>
                </Typography>
            )
        }

        return (
            <div>
                <Typography variant="subtitle2" color='textSecondary'>
                    {this.state.message}
                </Typography>
            </div>
        )
    }

}

export default Auth;